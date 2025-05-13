import os
from flask import Flask, jsonify, render_template_string, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

PGSOCKET_URI = os.environ.get("PGSOCKET_URI")

print(f"\n\nPGSOCKET_URI: {PGSOCKET_URI}\n\n")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = PGSOCKET_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)

@app.route("/users", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "name": user.name} for user in users])

@app.route("/", methods=["GET", "POST"])
def home():
    users = User.query.all()
    user_data = [(user.id, user.name) for user in users]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "remove":
            remove_id = request.form.get("remove_id")
            if remove_id:
                user_to_remove = User.query.get(remove_id)
                if user_to_remove:
                    db.session.delete(user_to_remove)
                    db.session.commit()
            return redirect(url_for("home"))

        new_name = request.form.get("name")
        if new_name:
            new_user = User(name=new_name)
            db.session.add(new_user)
            db.session.commit()
        return redirect(url_for("home"))

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>User List</title>
    </head>
    <body>
        <form method="POST">
            <input type="text" name="name" placeholder="Enter name" required>
            <button type="submit">Add User</button>
        </form>
        <br>
        <form method="POST">
            <input type="number" name="remove_id" placeholder="Enter ID to remove" required>
            <button type="submit" name="action" value="remove">Remove User</button>
        </form>
        <br>
        <h1>Users</h1>
        <ul>
            {% for user_id, name in user_data %}
                <li>{{ user_id }} - {{ name }}</li>
            {% endfor %}
        </ul>
    </body>
    </html>
    '''
    return render_template_string(html_template, user_data=user_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)