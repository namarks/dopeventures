from flask import Flask, request, jsonify
from dopetracks.frontend_interface.core_logic import process_user_inputs

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process():
    # Parse inputs from the macOS app
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    playlist_name = data.get('playlist_name')
    filepath = data.get('filepath', None)
    chat_name_text = data.get('chat_name_text', None)

    try:
        # Call the shared core logic function
        process_user_inputs(
            start_date=start_date,
            end_date=end_date,
            playlist_name=playlist_name,
            filepath=filepath,
            chat_name_text=chat_name_text
        )
        return jsonify({"success": True, "message": "Process completed successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8888, debug=True)
