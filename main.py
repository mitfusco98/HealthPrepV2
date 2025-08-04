from app import app
from routes import init_routes

# Initialize all routes
init_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
