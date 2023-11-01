from flask import Flask, jsonify

app = Flask(__name__)

# Sample data (a list of items)
items = [
    {"id": 1, "name": "Item 1"},
    {"id": 2, "name": "Item 2"},
    {"id": 3, "name": "Item 3"}
]

@app.route('/items', methods=['GET'])
def get_items():
    return jsonify({'items': items})

if __name__ == '__main__':
    app.run(debug=True)
