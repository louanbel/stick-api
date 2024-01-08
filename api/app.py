import datetime
import os

import psycopg2
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import create_access_token, JWTManager, get_jti, jwt_required, get_jwt, get_jwt_identity
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

CORS(app)

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

jwt = JWTManager(app)


@app.route('/boards/<int:board_id>', methods=['GET'])
@jwt_required()
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


def get_user_id_from_board(board_id, cursor):
    cursor.execute(
        "SELECT userId FROM boards WHERE id=%s;",
        (board_id,)
    )
    user_id = cursor.fetchone()

    if user_id:
        return user_id[0]
    else:
        return None


@app.route('/boards/delete/<int:board_id>', methods=['DELETE'])
@jwt_required()
def delete_board(board_id):
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    user_id_from_jwt = get_jwt_identity()

    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        user_id_from_board = get_user_id_from_board(board_id, cur)

        if user_id_from_board == user_id_from_jwt:
            cur.execute(
                "DELETE FROM board WHERE boardId=%s;",
                (board_id,)
            )
            cur.execute(
                "DELETE FROM boards WHERE id=%s;",
                (board_id,)
            )
            conn.commit()

            return jsonify({"message": "Board successfully deleted with ID: {}".format(board_id)})
        else:
            return jsonify({"message": "You are not allowed to delete this board"}), 403

    cur.close()
    conn.close()


@app.route('/partialBoards', methods=['GET'])
@jwt_required()
def get_partial_board_list():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)
    user_id = get_jwt_identity()
    data = []
    with conn.cursor() as cur:
        cur.execute("""
        SELECT boards.id, boards.name, boards.endTime, COALESCE(COUNT(board.id), 0) AS participantCount, boards.userId
        FROM boards
        LEFT JOIN board ON boardId = boards.id
        WHERE boards.userId = %s
        GROUP BY boards.id, boards.name, boards.endTime
        ORDER BY endTime;
        """, (user_id,))
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
@jwt_required()
def create_board():
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    # Get the data to create a new board from the request
    data = request.get_json()

    if not data:
        return jsonify({"message": "No data provided in the request body"}), 400

    user_id = get_jwt_identity()

    if "name" not in data or "endTime" not in data:
        return jsonify(
            {"message": "Invalid data format in request. 'name', 'endTime' fields are required."}), 400

    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO boards (name, endTime, userId) VALUES (%s, %s, %s) RETURNING id, name, endTime, userId;",
            (data["name"], data["endTime"], user_id)
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
        "userId": new_board_data[3],
    }

    return jsonify(response_data)


@app.route('/board/update-participants/<int:board_id>', methods=['PUT'])
@jwt_required()
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
@jwt_required()
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


@app.route('/board/delete-participant/<int:participant_id>', methods=['DELETE'])
@jwt_required()
def delete_participant(participant_id):
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
            "DELETE FROM board WHERE id=%s RETURNING id;",
            (participant_id,)
        )

        # Get the ID of the deleted item, if any
        deleted_item = cur.fetchone()

        if deleted_item is not None:
            deleted_item_id = deleted_item[0]
            conn.commit()
        else:
            conn.rollback()
            return jsonify({"message": "Participant with ID {} not found or could not be deleted.".format(participant_id)}), 404

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({"message": "Item successfully deleted with ID: {}".format(deleted_item_id)})


@app.route('/login', methods=['POST'])
def login():
    email: str = request.json.get('email', None)
    password: str = request.json.get('password', None)
    user_id: int = get_user_id_by_email(email)
    print(email, password)
    if verify_user(email, password):
        access_token = create_access_token(identity=user_id, expires_delta=datetime.timedelta(days=1))
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "Mauvais nom d'utilisateur ou mot de passe"}), 401


def verify_user(email, password):
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    try:
        cur = conn.cursor()

        cur.execute("SELECT password FROM users WHERE email = %s", (email,))

        user_data = cur.fetchone()
        cur.close()

        if user_data is not None:
            user_password_hash = user_data[0]
            print(user_password_hash, password)
            return check_password_hash(user_password_hash, password)

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

    return False


def get_user_id_by_email(email) -> int:
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    conn = psycopg2.connect(connection_string)

    try:
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))

        user_id = cur.fetchone()
        cur.close()

        if user_id is not None:
            return user_id[0]

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

    return None


@app.route('/register', methods=['POST'])
def register():
    email: str = request.json.get('email')
    password: str = request.json.get('password')

    # Vérifier si l'email ou le mot de passe n'est pas fourni
    if not email or not password:
        return jsonify({"msg": "Email and password are required"}), 400

    # Connexion à la base de données
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(connection_string)

    try:
        cur = conn.cursor()

        # Vérifier si l'utilisateur existe déjà
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify({"msg": "Email already used"}), 409

        # Hacher le mot de passe avant de le stocker
        hashed_password = generate_password_hash(password, 'pbkdf2')

        # Insérer le nouvel utilisateur dans la base de données
        cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_password))
        conn.commit()

        return jsonify({"msg": "Successfully registered the user"}), 201

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        return jsonify({"msg": "Error while registering user"}), 500

    finally:
        if conn is not None:
            conn.close()


@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']

    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()

        cur.execute("SELECT jti FROM blacklist WHERE jti = %s", (jti,))
        token_in_blacklist = cur.fetchone()

        return token_in_blacklist is not None


    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        # In case of an error, consider the JWT as blacklisted for safety reasons
        return True

    finally:
        cur.close()
        conn.close()


@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    current_jwt = get_jwt()

    jti = current_jwt['jti']

    expires_at = datetime.datetime.now() + datetime.timedelta(days=1)

    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()

        cur.execute("INSERT INTO blacklist (jti, expires_at) VALUES (%s, %s)", (jti, expires_at))
        conn.commit()

        return jsonify({"msg": "Successfully logged out"}), 200

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        return jsonify({"msg": "Error while login out"}), 500

    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    app.run(debug=True)
