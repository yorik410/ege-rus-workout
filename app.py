from flask import Flask, render_template
from accent.routes import bp as accent_bp
from letters.routes import bp as letters_bp

app = Flask(__name__)
app.secret_key = "secret"

app.register_blueprint(accent_bp)
app.register_blueprint(letters_bp)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
