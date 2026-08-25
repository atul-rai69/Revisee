def build_revision_prompt(title: str, description: str) -> str:
    return f"""
You are an expert educator.

Topic:
{title}

User Notes:
{description}

Tasks:

1. Create concise revision notes.
2. Create 5 key points.
3. Create 5 MCQs.
4. Each MCQ must have a question, exactly 4 options, the zero-based index
   of the correct option, an explanation, expected time in seconds, and a
   numeric difficulty (1 easy, 2 medium, 3 hard).

Return only one JSON value with no surrounding text.

Expected format:

{{
  "theory": "string",
  "key_points": ["string"],
  "questions": [
    {{
      "question": "string",
      "options": ["option1", "option2", "option3", "option4"],
      "correct_answer": 0,
      "explanation": "string",
      "expected_time": 30,
      "difficulty_level": 1
    }}
  ]
}}
"""
