# Assignment: Build a Simple LLM Query Tool

## Overview

**Time Allocation:** 4-6 hours  
**Submission:** A single Python file (`llm_query.py`) that runs successfully from the terminal

You will build a command-line tool that accepts a user question, sends it to the Claude API, and displays the response. No starter code is provided. You must write everything from scratch.

---

## Learning Objectives

By completing this assignment, you will demonstrate:

- Ability to set up a Python development environment
- Understanding of variables, strings, and functions
- Ability to work with external libraries
- Understanding of HTTP requests and JSON responses
- Basic error handling

---

## Requirements

### Core Functionality (Must Have)

1. Script prompts user to type a question
2. Script sends that question to the Claude API
3. Script prints Claude's response to the terminal
4. Script handles the case where the API key is missing or invalid

### Code Quality (Must Have)

5. Code includes comments explaining what each section does
6. API key is not hardcoded in the script (use environment variable)
7. Code runs without errors when proper API key is provided

### Stretch Goals (Optional)

8. Allow user to ask multiple questions in a loop until they type "quit"
9. Add a system prompt that gives Claude a persona
10. Print how many tokens were used in the response

---

## Constraints

- You **may** Google syntax questions (e.g., "python how to get environment variable")
- You may **NOT** copy working LLM API scripts from tutorials or GitHub
- You may **NOT** use AI to write code for you
- You **may** ask AI to explain concepts, error messages, or point you toward documentation

---

## Suggested Approach

1. Set up environment first (Python, IDE, API key) — don't count this toward your time
2. Write pseudocode in plain English before any Python
3. Build incrementally: first just print "hello world", then get user input, then add the API call
4. Test after every few lines

---

## Evaluation Rubric

| Criteria | Points |
|----------|--------|
| Script runs without crashing | 20 |
| Successfully calls Claude API and returns response | 30 |
| API key handled securely via environment variable | 15 |
| Graceful error handling (missing key, failed request) | 15 |
| Code is commented and readable | 10 |
| Stretch goals completed | 10 (bonus) |

**Total: 90 points + 10 bonus**

---

## Deliverables

1. `llm_query.py` — your completed script
2. A screenshot of the script running successfully with a sample question/answer

---

## Resources You'll Need to Find

- Anthropic API documentation (how to authenticate, endpoint URL, request format)
- Python `requests` library documentation
- How to access environment variables in Python

---

Good luck. Start with pseudocode.
