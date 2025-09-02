#!/bin/bash
# HealthPrep Start Examples - Hybrid Port Conflict Resolution

echo "🏥 HealthPrep Medical Screening System - Start Examples"
echo "=================================================="

echo ""
echo "📋 Available Start Methods:"
echo ""

echo "1️⃣  Standard Development (with basic port handling)"
echo "   python main.py"
echo "   → Uses PORT environment variable (default: 5000)"
echo "   → Basic port conflict fallback"
echo ""

echo "2️⃣  Smart Development (with advanced conflict resolution)"
echo "   USE_SMART_START=true python main.py"
echo "   → Advanced process cleanup"
echo "   → Intelligent port detection"
echo "   → Enhanced logging"
echo ""

echo "3️⃣  Direct Smart Start - Development"
echo "   python smart_start.py dev"
echo "   → Full hybrid approach"
echo "   → Process cleanup + port flexibility"
echo "   → Best for development with conflicts"
echo ""

echo "4️⃣  Production Preview (Gunicorn)"
echo "   python smart_start.py prod"
echo "   → Gunicorn server on port 5001"
echo "   → Production-like environment"
echo "   → Advanced cleanup and port handling"
echo ""

echo "5️⃣  Custom Port Configuration"
echo "   PORT=8080 python main.py"
echo "   PORT=8080 python smart_start.py dev"
echo "   PROD_PORT=8081 python smart_start.py prod"
echo ""

echo "🔧 Environment Variables:"
echo "   PORT          - Development server port (default: 5000)"
echo "   PROD_PORT     - Production preview port (default: 5001)"
echo "   USE_SMART_START - Enable smart conflict resolution (true/false)"
echo ""

echo "💡 Workflow Integration:"
echo "   Your existing workflows can use these approaches:"
echo "   - Modify workflow commands to include environment variables"
echo "   - Use smart_start.py for maximum conflict resolution"
echo "   - Combine with existing cleanup commands for best results"
echo ""

echo "🚨 Port Conflict Resolution Features:"
echo "   ✅ Automatic process cleanup (Python, Gunicorn, Flask)"
echo "   ✅ Smart port detection and fallback"
echo "   ✅ Environment-based configuration"
echo "   ✅ Integration with existing workflows"
echo "   ✅ Detailed logging and error handling"