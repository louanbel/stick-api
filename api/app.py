import os

import psycopg2
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

CORS(app)


@app.route('/boards/<int:board_id>', methods=['GET'])
def get_board(board_id):
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    board_data = {}
    participants = []

    with conn.cursor() as cur:
        cur.execute("""
        SELECT id, name, endTime
        FROM boards
        WHERE id=%s
        """, (board_id,))
        board_row = cur.fetchone()

        if board_row:
            board_data["id"] = board_row[0]
            board_data["name"] = board_row[1]
            board_data["endTime"] = board_row[2]

            cur.execute("""
            SELECT id, name, points
            FROM board
            WHERE boardId=%s
            ORDER BY points DESC;
            """, (board_id,))

            participant_rows = cur.fetchall()

            for row in participant_rows:
                participant = {
                    "id": row[0],
                    "name": row[1],
                    "points": row[2],
                }
                participants.append(participant)

    # Close the cursor and connection
    cur.close()
    conn.close()

    board_data["participants"] = participants

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify(board_data)

@app.route('/boards/delete/<int:board_id>', methods=['DELETE'])
def delete_board(board_id):
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM board WHERE boardId=%s;",
            (board_id,)
        )
        cur.execute(
            "DELETE FROM boards WHERE id=%s;",
            (board_id,)
        )

        # Commit the changes to the database
        conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Board successfully deleted with ID: {}".format(board_id)})


@app.route('/partialBoards', methods=['GET'])
def get_partial_board_list():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    data = []
    with conn.cursor() as cur:
        cur.execute("""
        SELECT boards.id, boards.name, boards.endTime, COALESCE(COUNT(board.id), 0) AS participantCount
        FROM boards
        LEFT JOIN board ON boardId = boards.id
        GROUP BY boards.id, boards.name, boards.endTime
        ORDER BY endTime;
        """)
        rows = cur.fetchall()

        for row in rows:
            item = {
                "id": row[0],
                "name": row[1],
                "endTime": row[2],
                "participantCount": row[3]
            }
            data.append(item)

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify(data)


@app.route('/board/create', methods=['POST'])
def create_board():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    # Get the data to create a new board from the request
    data = request.get_json()

    if not data:
        return jsonify({"message": "No data provided in the request body"}), 400

    if "name" not in data or "endTime" not in data:
        return jsonify({"message": "Invalid data format in request. 'name' and 'endTime' fields are required."}), 400

    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO boards (name, endTime) VALUES (%s, %s) RETURNING id, name, endTime;",
            (data["name"], data["endTime"])
        )

        # Get the data of the newly added board
        new_board_data = cur.fetchone()

        # Commit the changes to the database
        conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    # Prepare the response data
    response_data = {
        "id": new_board_data[0],
        "name": new_board_data[1],
        "endTime": new_board_data[2],
    }

    return jsonify(response_data)


@app.route('/board/update-participants/<int:board_id>', methods=['PUT'])
def update_board(board_id):
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
                    "UPDATE board SET name = %s, points = %s WHERE id = %s AND boardId = %s;",
                    (item["name"], item["points"], item["id"], board_id)
                )
            else:
                return jsonify({"message": "Invalid data format in request"}), 400

        # Commit the changes to the database
        conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Data updated successfully"})


@app.route('/board/add-participant/<int:board_id>', methods=['POST'])
def add_participant(board_id):
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
            "INSERT INTO board (name, points, boardId) VALUES (%s, %s, %s) RETURNING id;",
            (data["name"], data["points"], board_id)
        )

        # Get the ID of the newly added item
        new_item_id = cur.fetchone()[0]

        # Commit the changes to the database
        conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Item added successfully with ID: {}".format(new_item_id)})


@app.route('/board/delete-participant/<int:board_id>', methods=['DELETE'])
def delete_item(board_id):
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    # Get the data to add from the request
    data = request.get_json()

    if not data:
        return jsonify({"message": "No data provided in the request body"}), 400

    if "id" not in data:
        return jsonify({"message": "Invalid data format in request. 'id' fields are required."}), 400

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM board WHERE id=%s AND boardId=%s RETURNING id;",
            (data["id"], board_id)
        )

        # Get the ID of the deleted item, if any
        deleted_item = cur.fetchone()

        if deleted_item is not None:
            deleted_item_id = deleted_item[0]
            conn.commit()
        else:
            conn.rollback()
            return jsonify({"message": "Item with ID {} not found or could not be deleted.".format(board_id)}), 404

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Item successfully deleted with ID: {}".format(deleted_item_id)})


if __name__ == '__main__':
    app.run(debug=True)
