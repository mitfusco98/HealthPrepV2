"""
Screening Catalog Service Layer
Universal screening type management with fuzzy detection and variant system
"""
import re
import json
import difflib
from typing import Dict, List, Optional, Tuple
from sqlalchemy import or_, and_, func
from models import (
    db, UniversalType, UniversalTypeAlias, ScreeningProtocol, 
    ScreeningVariant, TypeLabelAssociation, ScreeningType,
    User, Organization
)


class LabelNormalizer:
    """Handles label normalization and fuzzy matching"""
    
    # Common medical abbreviation expansions
    EXPANSIONS = {
        'dxa': 'dexa',
        'dexascan': 'dexa',
        'ekg': 'ecg',
        'cxr': 'chest x-ray',
        'ct': 'computed tomography',
        'mri': 'magnetic resonance imaging',
        'cbc': 'complete blood count',
        'bmp': 'basic metabolic panel',
        'cmp': 'comprehensive metabolic panel',
        'lft': 'liver function test',
        'tsh': 'thyroid stimulating hormone',
        'psa': 'prostate specific antigen',
        'hgb': 'hemoglobin',
        'hct': 'hematocrit',
        'bp': 'blood pressure'
    }
    
    # Common stopwords to remove (when safe)
    STOPWORDS = {'test', 'testing', 'scan', 'scanning', 'screen', 'screening', 'check', 'the', 'of'}
    
    @classmethod
    def normalize_label(cls, label: str) -> str:
        """Normalize label for consistent matching"""
        if not label:
            return ""
        
        # Lowercase and trim
        normalized = label.lower().strip()
        
        # Replace punctuation and separators with spaces
        normalized = re.sub(r'[_\-\./\\]+', ' ', normalized)
        
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Apply abbreviation expansions
        tokens = normalized.split()
        expanded_tokens = []
        
        for token in tokens:
            # Skip very short tokens unless they're known abbreviations
            if len(token) < 2 and token not in cls.EXPANSIONS:
                continue
            
            # Apply expansion
            expanded = cls.EXPANSIONS.get(token, token)
            
            # Skip common stopwords (but keep medical terms)
            if token not in cls.STOPWORDS or token in cls.EXPANSIONS:
                if isinstance(expanded, str):
                    expanded_tokens.extend(expanded.split())
                else:
                    expanded_tokens.append(expanded)
        
        return ' '.join(expanded_tokens)
    
    @classmethod
    def create_slug(cls, name: str) -> str:
        """Create URL-friendly slug from name"""
        normalized = cls.normalize_label(name)
        # Replace spaces with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', normalized)
        # Remove multiple hyphens and trim
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug
    
    @classmethod
    def fuzzy_match_ratio(cls, a: str, b: str) -> float:
        """Calculate fuzzy match ratio between two labels (0-1)"""
        norm_a = cls.normalize_label(a)
        norm_b = cls.normalize_label(b)
        
        if not norm_a or not norm_b:
            return 0.0
        
        # Use SequenceMatcher for similarity
        return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    
    @classmethod
    def token_set_ratio(cls, a: str, b: str) -> float:
        """Calculate token set ratio for partial matching"""
        norm_a = set(cls.normalize_label(a).split())
        norm_b = set(cls.normalize_label(b).split())
        
        if not norm_a or not norm_b:
            return 0.0
        
        # Calculate intersection over union
        intersection = len(norm_a.intersection(norm_b))
        union = len(norm_a.union(norm_b))
        
        if union == 0:
            return 0.0
        
        return intersection / union


class ScreeningCatalogService:
    """Main service for universal screening type management"""
    
    def __init__(self):
        self.normalizer = LabelNormalizer()
        self.fuzzy_threshold = 0.87  # Confidence threshold for fuzzy matches
    
    def resolve_universal_type(self, label: str, user_org_id: int = None) -> Dict:
        """
        Resolve a label to a universal type using multiple matching strategies
        Returns dict with match type and results
        """
        if not label:
            return {"match": "invalid", "reason": "Empty label"}
        
        normalized = self.normalizer.normalize_label(label)
        slug = self.normalizer.create_slug(label)
        
        # 1. Exact slug match
        ut = UniversalType.query.filter_by(slug=slug, status='active').first()
        if ut:
            return {"match": "exact", "universal_type": ut, "confidence": 1.0}
        
        # 2. Exact alias match
        alias = UniversalTypeAlias.query.join(UniversalType).filter(
            UniversalTypeAlias.alias == normalized,
            UniversalType.status == 'active'
        ).first()
        if alias:
            return {"match": "alias", "universal_type": alias.universal_type, "confidence": alias.confidence}
        
        # 3. Label association match
        association = TypeLabelAssociation.query.join(UniversalType).filter(
            TypeLabelAssociation.label == normalized,
            UniversalType.status == 'active'
        ).first()
        if association:
            return {"match": "association", "universal_type": association.universal_type, "confidence": 0.85}
        
        # 4. Fuzzy matching against canonical names and aliases
        candidates = self._find_fuzzy_candidates(normalized, limit=5)
        if candidates:
            # Return best match if above threshold
            best_candidate = candidates[0]
            if best_candidate['confidence'] >= self.fuzzy_threshold:
                return {"match": "fuzzy", "universal_type": best_candidate['universal_type'], 
                       "confidence": best_candidate['confidence'], "candidates": candidates}
            else:
                return {"match": "fuzzy_low", "candidates": candidates}
        
        # 5. Unresolved
        return {"match": "unresolved", "normalized_label": normalized}
    
    def _find_fuzzy_candidates(self, normalized_label: str, limit: int = 5) -> List[Dict]:
        """Find fuzzy match candidates for a normalized label"""
        candidates = []
        
        # Get all active universal types with their aliases
        universal_types = UniversalType.query.filter_by(status='active').all()
        
        for ut in universal_types:
            # Check against canonical name
            canonical_ratio = self.normalizer.fuzzy_match_ratio(normalized_label, ut.canonical_name)
            token_ratio = self.normalizer.token_set_ratio(normalized_label, ut.canonical_name)
            confidence = max(canonical_ratio, token_ratio)
            
            if confidence > 0.5:  # Minimum threshold for consideration
                candidates.append({
                    'universal_type': ut,
                    'confidence': confidence,
                    'match_text': ut.canonical_name,
                    'match_type': 'canonical'
                })
            
            # Check against aliases
            for alias in ut.aliases:
                alias_ratio = self.normalizer.fuzzy_match_ratio(normalized_label, alias.alias)
                token_ratio = self.normalizer.token_set_ratio(normalized_label, alias.alias)
                confidence = max(alias_ratio, token_ratio) * alias.confidence  # Factor in alias confidence
                
                if confidence > 0.5:
                    candidates.append({
                        'universal_type': ut,
                        'confidence': confidence,
                        'match_text': alias.alias,
                        'match_type': 'alias'
                    })
        
        # Sort by confidence and deduplicate
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        seen_uts = set()
        unique_candidates = []
        
        for candidate in candidates:
            if candidate['universal_type'].id not in seen_uts:
                unique_candidates.append(candidate)
                seen_uts.add(candidate['universal_type'].id)
                if len(unique_candidates) >= limit:
                    break
        
        return unique_candidates
    
    def ensure_protocol(self, universal_type_id: str, org_id: int = None, 
                       scope: str = 'system', name: str = None) -> ScreeningProtocol:
        """Ensure a protocol exists for the given universal type and scope"""
        # Look for existing protocol
        query = ScreeningProtocol.query.filter_by(
            universal_type_id=universal_type_id,
            scope=scope
        )
        
        if scope == 'org' and org_id:
            query = query.filter_by(org_id=org_id)
        elif scope == 'system':
            query = query.filter(ScreeningProtocol.org_id.is_(None))
        
        protocol = query.first()
        
        if not protocol:
            # Create new protocol
            ut = UniversalType.query.get(universal_type_id)
            protocol_name = name or ut.canonical_name
            
            protocol = ScreeningProtocol(
                universal_type_id=universal_type_id,
                name=protocol_name,
                scope=scope,
                org_id=org_id if scope == 'org' else None,
                created_by=1  # TODO: Get from current user context
            )
            db.session.add(protocol)
            db.session.flush()  # Get ID
        
        return protocol
    
    def upsert_variant(self, protocol_id: str, author_user_id: int, org_id: int,
                      criteria_json: Dict, label: str, derived_from: str = None) -> ScreeningVariant:
        """Create or update a screening variant"""
        criteria_hash = ScreeningVariant.compute_criteria_hash(criteria_json)
        
        # Check for existing variant by the same author
        existing = ScreeningVariant.query.filter_by(
            protocol_id=protocol_id,
            author_user_id=author_user_id,
            criteria_hash=criteria_hash
        ).first()
        
        if existing:
            # Update existing variant
            existing.label = label
            existing.criteria_json = criteria_json
            existing.updated_at = db.func.now()
            return existing
        
        # Create new variant
        variant = ScreeningVariant(
            protocol_id=protocol_id,
            author_user_id=author_user_id,
            org_id=org_id,
            label=label,
            criteria_json=criteria_json,
            criteria_hash=criteria_hash,
            derived_from_variant_id=derived_from,
            is_published=True  # Default to published for admin creation
        )
        
        db.session.add(variant)
        return variant
    
    def list_variants_by_scope(self, admin_user: User, filters: Dict = None) -> Dict:
        """
        List variants within admin's scope with optional filters
        Returns organized data structure for UI
        """
        filters = filters or {}
        
        # Compute admin scope
        if admin_user.role == 'root_admin':
            # Root admin sees all orgs
            org_ids = [org.id for org in Organization.query.all()]
        else:
            # Org admin sees their org only
            org_ids = [admin_user.org_id] if admin_user.org_id else []
        
        # Base query for variants in scope
        query = ScreeningVariant.query.join(ScreeningProtocol).join(UniversalType).filter(
            or_(
                ScreeningVariant.org_id.in_(org_ids),
                ScreeningProtocol.scope == 'system'
            )
        )
        
        # Apply filters
        if filters.get('user_id'):
            query = query.filter(ScreeningVariant.author_user_id == filters['user_id'])
        
        if filters.get('org_id') and filters['org_id'] in org_ids:
            query = query.filter(ScreeningVariant.org_id == filters['org_id'])
        
        if filters.get('universal_type_id'):
            query = query.filter(ScreeningProtocol.universal_type_id == filters['universal_type_id'])
        
        if filters.get('published_only'):
            query = query.filter(ScreeningVariant.is_published == True)
        
        variants = query.order_by(
            UniversalType.canonical_name,
            ScreeningProtocol.name,
            ScreeningVariant.updated_at.desc()
        ).all()
        
        # Organize by Universal Type → Protocol → Variants
        organized = {}
        
        for variant in variants:
            ut = variant.protocol.universal_type
            protocol = variant.protocol
            
            if ut.id not in organized:
                organized[ut.id] = {
                    'universal_type': ut,
                    'protocols': {}
                }
            
            if protocol.id not in organized[ut.id]['protocols']:
                organized[ut.id]['protocols'][protocol.id] = {
                    'protocol': protocol,
                    'variants': []
                }
            
            organized[ut.id]['protocols'][protocol.id]['variants'].append(variant)
        
        return organized
    
    def create_preset_from_variant(self, variant_id: str, preset_name: str, 
                                  target_scope: str = 'org', org_id: int = None,
                                  created_by: int = None) -> 'ScreeningPreset':
        """Create a preset from a screening variant"""
        from models import ScreeningPreset
        from datetime import datetime
        
        variant = ScreeningVariant.query.get(variant_id)
        if not variant:
            raise ValueError("Variant not found")
        
        # Convert variant criteria to preset format
        criteria = variant.criteria_json
        screening_data = [{
            'name': variant.label,
            'description': f'Generated from {variant.protocol.universal_type.canonical_name}',
            'keywords': criteria.get('keywords', []),
            'gender_criteria': criteria.get('eligible_genders', 'both'),
            'age_min': criteria.get('min_age'),
            'age_max': criteria.get('max_age'),
            'frequency_number': criteria.get('frequency_number', 1),
            'frequency_unit': criteria.get('frequency_unit', 'years'),
            'trigger_conditions': criteria.get('trigger_conditions', []),
            'is_active': True
        }]
        
        preset_data = {
            'name': preset_name,
            'description': f'Created from variant: {variant.label}',
            'specialty': 'Custom',
            'version': '2.0',
            'created_date': datetime.utcnow().isoformat(),
            'screening_types': screening_data
        }
        
        preset = ScreeningPreset(
            name=preset_name,
            description=preset_data['description'],
            specialty='Custom',
            org_id=org_id if target_scope == 'org' else None,
            shared=target_scope == 'global',
            preset_scope=target_scope,
            screening_data=preset_data,
            preset_metadata={
                'source_variant_id': variant_id,
                'source_protocol_id': variant.protocol_id,
                'source_universal_type_id': variant.protocol.universal_type_id,
                'created_from': 'variant',
                'extraction_method': 'from_variant'
            },
            created_by=created_by
        )
        
        db.session.add(preset)
        return preset
    
    def link_labels(self, universal_type_id: str, labels: List[str], created_by: int) -> List[TypeLabelAssociation]:
        """Link multiple labels to a universal type"""
        associations = []
        
        for label in labels:
            normalized = self.normalizer.normalize_label(label)
            if not normalized:
                continue
            
            # Check if association already exists
            existing = TypeLabelAssociation.query.filter_by(
                label=normalized,
                universal_type_id=universal_type_id
            ).first()
            
            if not existing:
                association = TypeLabelAssociation(
                    label=normalized,
                    universal_type_id=universal_type_id,
                    source='org_admin',
                    created_by=created_by
                )
                db.session.add(association)
                associations.append(association)
        
        return associations
    
    def migrate_existing_screening_types(self, batch_size: int = 100) -> Dict:
        """
        Migrate existing screening types to the universal type system
        Returns statistics about the migration
        """
        stats = {
            'universal_types_created': 0,
            'protocols_created': 0,
            'variants_created': 0,
            'labels_associated': 0,
            'errors': []
        }
        
        try:
            # Process screening types in batches
            offset = 0
            
            while True:
                screening_types = ScreeningType.query.offset(offset).limit(batch_size).all()
                if not screening_types:
                    break
                
                for st in screening_types:
                    try:
                        # Resolve or create universal type
                        resolution = self.resolve_universal_type(st.name, st.org_id)
                        
                        if resolution['match'] == 'unresolved':
                            # Create new universal type
                            canonical_name = st.name.title()  # Normalize case
                            slug = UniversalType.create_slug(canonical_name)
                            
                            ut = UniversalType(
                                canonical_name=canonical_name,
                                slug=slug,
                                status='active',
                                created_by=1  # System migration
                            )
                            db.session.add(ut)
                            db.session.flush()
                            stats['universal_types_created'] += 1
                        else:
                            ut = resolution['universal_type']
                        
                        # Ensure protocol exists
                        protocol = self.ensure_protocol(
                            universal_type_id=ut.id,
                            org_id=st.org_id,
                            scope='org' if st.org_id else 'system',
                            name=ut.canonical_name
                        )
                        if protocol.id not in [p.id for p in ut.protocols]:
                            stats['protocols_created'] += 1
                        
                        # Create variant from screening type
                        criteria_json = {
                            'name': st.name,
                            'keywords': st.keywords_list,
                            'eligible_genders': st.eligible_genders or 'both',
                            'min_age': st.min_age,
                            'max_age': st.max_age,
                            'frequency_years': st.frequency_years or 1.0,
                            'trigger_conditions': st.trigger_conditions_list,
                            'is_active': st.is_active
                        }
                        
                        variant = self.upsert_variant(
                            protocol_id=protocol.id,
                            author_user_id=st.created_by or 1,
                            org_id=st.org_id,
                            criteria_json=criteria_json,
                            label=st.name
                        )
                        stats['variants_created'] += 1
                        
                        # Create label association if needed
                        normalized_label = self.normalizer.normalize_label(st.name)
                        if not TypeLabelAssociation.query.filter_by(
                            label=normalized_label,
                            universal_type_id=ut.id
                        ).first():
                            association = TypeLabelAssociation(
                                label=normalized_label,
                                universal_type_id=ut.id,
                                source='system',
                                created_by=1
                            )
                            db.session.add(association)
                            stats['labels_associated'] += 1
                        
                    except Exception as e:
                        stats['errors'].append(f"Error processing {st.name}: {str(e)}")
                        continue
                
                # Commit batch
                db.session.commit()
                offset += batch_size
            
        except Exception as e:
            db.session.rollback()
            stats['errors'].append(f"Migration failed: {str(e)}")
        
        return stats


# Service instance for use in routes
screening_catalog = ScreeningCatalogService()