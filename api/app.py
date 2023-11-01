from flask import Flask, request, jsonify
import os
import psycopg2
from dotenv import load_dotenv
from flask_cors import CORS


app = Flask(__name__)

CORS(app)

@app.route('/items', methods=['GET'])
def get_items():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    data = []
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, points FROM board ORDER BY points DESC;")
        rows = cur.fetchall()

        for row in rows:
            item = {
                "id": row[0],
                "name": row[1],
                "points": row[2]
            }
            data.append(item)

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify(data)

@app.route('/items', methods=['PUT'])
def update_items():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    # Get the data to update from the request
    data = request.get_json()

    if not data:
        return jsonify({"message": "No data provided in the request body"}), 400

    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        for item in data:
            if "id" in item and "name" in item and "points" in item:
                cur.execute(
                    "UPDATE board SET name = %s, points = %s WHERE id = %s;",
                    (item["name"], item["points"], item["id"])
                )
            else:
                return jsonify({"message": "Invalid data format in request"}), 400

        # Commit the changes to the database
        conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Data updated successfully"})

@app.route('/items', methods=['POST'])
def add_item():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    # Get the data to add from the request
    data = request.get_json()

    if not data:
        return jsonify({"message": "No data provided in the request body"}), 400

    if "name" not in data or "points" not in data:
        return jsonify({"message": "Invalid data format in request. 'name' and 'points' fields are required."}), 400

    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO board (name, points) VALUES (%s, %s) RETURNING id;",
            (data["name"], data["points"])
        )

        # Get the ID of the newly added item
        new_item_id = cur.fetchone()[0]

        # Commit the changes to the database
        conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Item added successfully with ID: {}".format(new_item_id)})

if __name__ == '__main__':
    app.run(debug=True)
