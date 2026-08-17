def build_revision_prompt(
    title: str,
    description: str
) -> str:

    return f"""
You are an expert educator.

Topic:
{title}

User Notes:
{description}

Tasks:

1. Create concise revision notes.
2. Create 5 key points.
3. Create 5  MCQs.
4. Each MCQ must have:
   - question
   - 4 options
   - index of the correct option in the options list
   - explanation of correct_answer
   - expected time to solve the question in seconds
   - difficulty level in number 1 for easy , 2 for medium, 3 for hard

Return ONLY  JSON value strictly remove any text before or after JSON value.

Expected Format:

{{
  "theory": "string",
  "key_points": ["string"],
  "questions": [
    {{
      "question": "string",
      "options": [
        "option1",
        "option2",
        "option3",
        "option4"
      ],
      "correct_answer": "number",
      "explanation": "string",
      "expected_time": "number",
      "difficulty_level: "number"
    }}
  ]
}}
"""