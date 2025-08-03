
import subprocess
import re
import time
import os

class AutoDebugger:
    """Automated debugging helper for common Python/Flask errors"""
    
    def __init__(self):
        self.common_fixes = {
            r"cannot import name '(\w+)' from '([\w\.]+)'": self.fix_missing_import,
            r"No module named '(\w+)'": self.fix_missing_module,
            r"name '(\w+)' is not defined": self.fix_undefined_name,
            r"AttributeError: module '(\w+)' has no attribute '(\w+)'": self.fix_missing_attribute
        }
    
    def run_and_debug(self, command="python init_db.py", max_attempts=5):
        """Run command and automatically fix common errors"""
        attempts = 0
        
        while attempts < max_attempts:
            print(f"Attempt {attempts + 1}: Running {command}")
            
            try:
                result = subprocess.run(
                    command.split(), 
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
                
                if result.returncode == 0:
                    print("✅ Success! Application started without errors.")
                    print(result.stdout)
                    return True
                
                error_output = result.stderr
                print(f"❌ Error detected:\n{error_output}")
                
                # Try to fix the error
                if self.attempt_fix(error_output):
                    print("🔧 Applied potential fix, retrying...")
                    attempts += 1
                    time.sleep(2)
                else:
                    print("❓ Could not automatically fix this error.")
                    break
                    
            except subprocess.TimeoutExpired:
                print("⏰ Command timed out")
                break
            except Exception as e:
                print(f"💥 Unexpected error: {e}")
                break
        
        print(f"❌ Failed to auto-fix after {attempts} attempts")
        return False
    
    def attempt_fix(self, error_output):
        """Try to fix error based on patterns"""
        for pattern, fix_function in self.common_fixes.items():
            match = re.search(pattern, error_output)
            if match:
                try:
                    return fix_function(match, error_output)
                except Exception as e:
                    print(f"Fix attempt failed: {e}")
                    return False
        return False
    
    def fix_missing_import(self, match, error_output):
        """Fix missing import errors"""
        missing_name = match.group(1)
        module_path = match.group(2)
        
        print(f"🔍 Missing import: {missing_name} from {module_path}")
        
        # Common fixes for missing imports
        if "FuzzyMatcher" in missing_name:
            return self.add_missing_class(module_path, missing_name, "FuzzyMatcher")
        elif "DocumentUploadForm" in missing_name:
            return self.add_missing_class("forms", missing_name, "DocumentUploadForm")
        elif "AdminConfig" in missing_name:
            return self.add_missing_class("admin.config", missing_name, "AdminConfig")
        
        return False
    
    def fix_missing_module(self, match, error_output):
        """Fix missing module errors"""
        module_name = match.group(1)
        print(f"🔍 Missing module: {module_name}")
        return False
    
    def fix_undefined_name(self, match, error_output):
        """Fix undefined name errors"""
        name = match.group(1)
        print(f"🔍 Undefined name: {name}")
        return False
    
    def fix_missing_attribute(self, match, error_output):
        """Fix missing attribute errors"""
        module = match.group(1)
        attribute = match.group(2)
        print(f"🔍 Missing attribute: {module}.{attribute}")
        return False
    
    def add_missing_class(self, module_path, class_name, template_type):
        """Add a missing class to a module"""
        file_path = module_path.replace('.', '/') + '.py'
        
        if not os.path.exists(file_path):
            print(f"❌ Module file not found: {file_path}")
            return False
        
        print(f"✏️ Adding {class_name} to {file_path}")
        # This would contain the logic to add the missing class
        # For now, just indicate that manual intervention is needed
        return False

if __name__ == "__main__":
    debugger = AutoDebugger()
    debugger.run_and_debug()
