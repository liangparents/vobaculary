import openai
from flask import Flask, request, render_template, session
import sqlite3
import logging

# Set your OpenAI API key
openai.api_key = ""

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "supersecretkey"
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

def setup_database():
    conn = sqlite3.connect('test_results.db')
    cursor = conn.cursor()
    
    # Create table with new columns for tested_date and failed_times
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS failed_answers (
            id INTEGER PRIMARY KEY,
            question TEXT,
            child_answer TEXT,
            correct_answer TEXT,
            explanation TEXT,
            tested_date TEXT,  -- Store date in 'YYYY-MM-DD' format
            failed_times INTEGER DEFAULT 1  -- Default failure count is 1
        )
    ''')
    
    conn.commit()
    conn.close()


setup_database()

# Function to generate a vocabulary question using the OpenAI chat model
def generate_question(question_type):
    question_prompt={
        "Sentence_Completion":"Create a Sentence Completion question for vocabulary battery with four answer options and indicate the correct one",
        "Verbal_Classification":"Create a Verbal Classification question for vocabulary battery with four answer options and indicate the correct one",
        "Verbal_Analogies":"Create a sentence completion question for vocabulary battery with four answer options and indicate the correct one"
        }
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a tutor creating a multiple-choice question for a 5th grader for California GATE. Please make sure it's challenging. Format it as follows:\n\nQuestion: <question text>\nA) <option1>\nB) <option2>\nC) <option3>\nCorrect answer: <correct answer letter>"},
            {"role": "user", "content": question_prompt[question_type]}
        ]
    )
    return response.choices[0].message.content

# Function to explain why the correct answer is right
def get_explanation(question, correct_answer):
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a tutor creating a multiple-choice vocabulary question for a 5th grader."},
            {"role": "user", "content": f"Explain why the answer to '{question}' is '{correct_answer}'."}
        ]
    )
    return response.choices[0].message.content

import sqlite3
from datetime import datetime

def save_failed_answer(question, child_answer, correct_answer, explanation):
    conn = sqlite3.connect('test_results.db')
    cursor = conn.cursor()

    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')

    # Check if the same question already exists
    cursor.execute('''
        SELECT failed_times FROM failed_answers 
        WHERE correct_answer = ?
    ''', (correct_answer,))
    
    row = cursor.fetchone()

    if row:
        # Increment failed_times if the question exists
        failed_times = row[0] + 1
        cursor.execute('''
            UPDATE failed_answers 
            SET failed_times = ?, tested_date = ? 
            WHERE question = ? AND correct_answer = ?
        ''', (failed_times, today, question, correct_answer))
    else:
        # Insert a new record if the question does not exist
        cursor.execute('''
            INSERT INTO failed_answers (
                question, child_answer, correct_answer, explanation, tested_date, failed_times
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (question, child_answer, correct_answer, explanation, today, 1))

    conn.commit()
    conn.close()


# Flask route to display the home page and handle form submissions
@app.route("/", methods=["GET", "POST"])
def home():
    question_type = None  # Initialize question_type here

    if request.method == "POST":
        question_type = request.form["question_type"] 
        logging.debug(f'Selected question type: {question_type}')
        child_answer = request.form["answer"].strip()
        question = session.get("question")
        correct_answer = session.get("correct_answer")
        
        logging.debug(f'child_answer: {child_answer.strip().lower()}, correct_answer: {correct_answer.strip().lower()[0]}')
        
        if child_answer.strip().lower() != correct_answer.strip().lower()[0]:
            explanation = get_explanation(question, correct_answer)
            save_failed_answer(question, child_answer, correct_answer, explanation)
            return render_template(
                "result.html", correct=False, explanation=explanation, correct_answer=correct_answer
            )
        else:
            return render_template("result.html", correct=True)

    # Ensure question_type is set before generating a question
    if question_type is None:  
        # Default question type or handle as appropriate
        question_type = "Sentence_Completion"  # You can change this to whatever default you prefer

    # Generate a new question and store it in the session
    question_text = generate_question(question_type)
    
    # Ensure the format is correct
    if "Correct answer: " not in question_text:
        logging.error("Error: Invalid question format")
        return "Error: Invalid question format", 500  # Return error response
    
    question, correct_answer = question_text.split("Correct answer: ")
    session["question"] = question.strip()
    session["correct_answer"] = correct_answer.strip()

    # Return the question page
    return render_template("question.html", question=question.strip())


@app.route("/report", methods=["GET"])
def show_report():
    conn = sqlite3.connect('test_results.db')
    cursor = conn.cursor()

    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')

    # Query for all failed answers from today
    cursor.execute('''
        SELECT question, child_answer, correct_answer, explanation, failed_times 
        FROM failed_answers 
        WHERE tested_date = ?
    ''', (today,))

    results = cursor.fetchall()
    conn.close()

    return render_template("report.html", results=results)


if __name__ == "__main__":
    app.run(debug=True)
