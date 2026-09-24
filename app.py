import csv
import io
import sqlite3
import hashlib
from flask import Flask, jsonify, request
from database import get_connection

app = Flask(__name__)

@app.route("/import", methods=["POST"])
def import_csv():
    # Check if the request includes a file
    if "file" not in request.files:
        return jsonify({"error": "Please attach CSV file with key 'file'"}), 400

    file = request.files["file"]

    # Check if user choose empty file
    if file.filename == "":
        return jsonify({"error": "No files have been selected for upload yet"}), 400
    
    try:
        file_content = file.stream.read()

        file_checksum = hashlib.sha256(file_content).hexdigest()

        stream = io.StringIO(
            file_content.decode("utf-8"),
            newline = None
        )
        csv_reader = csv.DictReader(stream)

        print("File checksum:", file_checksum)

    except Exception as e:
        return jsonify({"error": f"Can not read CSV file: {str(e)}"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM imported_files WHERE checksum = ?",
        (file_checksum,)
    )

    if cursor.fetchone() is not None:
        conn.close()

        return jsonify({
            "error": "This file has already been imported",
            "checksum": file_checksum
        }), 409

    # Initialize counter variables to statistically analyze the results
    total_rows = 0
    imported_count = 0
    invalid_rows = []
    duplicate_rows = []

    # Temporary list to catch duplicates directly within the CSV file
    seen_emails_in_file = set()

    # Trarvesal every lines in CSV file
    for row_idx, row in enumerate(csv_reader, start=1):
        total_rows += 1
        name = row.get("name", "").strip() if row.get("name") else ""
        email = row.get("email", "").strip() if row.get("email") else ""
        age_raw = row.get("age", "").strip() if row.get("age") else ""

        # Check invalid rows
        # Check for missing name or email
        if not name or not email:
            invalid_rows.append({"row": row_idx, "data": row, "reason": "Missing name or email"})
            continue

        # Check data type of age
        age = None
        if age_raw:
            try:
                age = int(age_raw)
                if age < 0 or age > 120:
                    invalid_rows.append({"row": row_idx, "data": row, "reason": "Invalid age (0-120)"})
                    continue
            except ValueError:
                invalid_rows.append({"row": row_idx, "data": row, "reason": "Age must be Integer"})
                continue

        # Check for duplicate rows
        # Check for duplicate with the previous line directly in the CSV file     
        if email in seen_emails_in_file:
            duplicate_rows.append({"row": row_idx, "data": row, "reason": "Email duplicated in CSV file"})
            continue

        # Check for duplicates with the existing data in SQLite
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone() is not None:
            duplicate_rows.append({"row": row_idx, "data": row, "reason": "Email is already existed in Database"})
            continue      

        # INSERT: Add valid line to SQLite
        try:
            cursor.execute(
                "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                (name, email, age)
            )
            seen_emails_in_file.add(email)
            imported_count += 1

        except sqlite3.IntegrityError as e:
            duplicate_rows.append({
                "row": row_idx,
                "data": row,
                "reason": str(e)
            })

        except sqlite3.Error as e:
            conn.rollback()
            conn.close()

            return jsonify({
                "error": "Database error while importing user",
                "detail": str(e)
            }), 500
        
        except Exception as e:
            conn.rollback()
            conn.close()

            return jsonify({
                "error": "Unexpected error while importing user",
                "detail": str(e)
            }), 500

    # Save the imported file checksum
    cursor.execute(
        "INSERT INTO imported_files (filename, checksum) VALUES (?, ?)",
        (file.filename, file_checksum)
    )

    # Save all the changes to DB and close connection
    conn.commit()
    conn.close()

    # Return detailed JSON result
    return jsonify({
        "message": "The import process is complete",
        "summary": {
            "total_rows": total_rows,
            "imported": imported_count,
            "invalid_count": len(invalid_rows),
            "duplicate_count": len(duplicate_rows)
        },
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_rows
    }), 200

@app.route("/display", methods=["GET"])
def display_data():
    page = request.args.get("page", default=1, type=int)
    limit = request.args.get("limit", default=10, type=int)

    if page < 1:
        return jsonify({
            "error": "Page must be greater than 0"
        }), 400

    if limit < 1 or limit > 100:
        return jsonify({
            "error": "Limit must be between 1 and 100"
        }), 400

    offset = (page - 1) * limit

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_records = cursor.fetchone()["total"]

    # Retrieve all the record from users table
    cursor.execute("""
        SELECT id, name, email, age 
        FROM users
        ORDER BY id
        LIMIT ? OFFSET ?
        """, (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()

    # Transform SQLite Row data to dictionary list
    users_list = []
    for row in rows:
        users_list.append({
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "age": row["age"]
        })

    total_pages = (total_records + limit - 1) // limit
    
    return jsonify({
        "pagination": {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages
        },
        "data": users_list
    }), 200

if __name__ == "__main__":
    app.run(debug=True)