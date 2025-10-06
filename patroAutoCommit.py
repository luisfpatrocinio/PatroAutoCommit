# ==============================================================================
# PatroAutoCommit - AI-Powered Git Commit Message Generator
#
# Author: Luis Felipe Patrocinio
# GitHub: https://github.com/luisfpatrocinio
#
# This script automates the process of writing Git commit messages.
# It reads staged changes, generates a descriptive commit message using the
# Google Gemini API, and provides an interactive prompt to commit the changes.
# ==============================================================================


# --- 1. IMPORTS ---
# Standard library imports for system, file, and subprocess management.
import os
import sys
import subprocess
from typing import Optional

# Third-party imports for API interaction and environment variable loading.
import google.generativeai as genai
from dotenv import load_dotenv


# --- 2. CONFIGURATION ---
# Load environment variables (like GEMINI_API_KEY) from a .env file.
load_dotenv()

# Maximum size for the git diff in characters (bytes).
# This helps prevent sending excessively large and costly requests to the API.
MAX_DIFF_SIZE = 80000


# --- 3. HELPER FUNCTIONS ---
# Small, reusable utility functions used throughout the script.

def colored_print(text: str, color: str = "green"):
    """
    Prints colored text to the console for a better user experience.
    
    Args:
        text (str): The text to print.
        color (str): The color to use ('green', 'red', 'yellow').
    """
    colors = {
        "green": "\033[0;32m",
        "red": "\033[0;31m",
        "yellow": "\033[0;93m",
        "end": "\033[0m",
    }
    color_code = colors.get(color, colors["green"])
    sys.stdout.write(f"{color_code}{text}{colors['end']}")
    sys.stdout.flush()

def handle_push():
    """Asks the user if they want to push the changes and executes the command."""
    while True:
        colored_print("\nDo you want to push the changes? (y/n) ", "yellow")
        choice = input().lower()
        if choice in ['y', 's']:
            colored_print("║ Pushing changes...\n")
            run_git_command(["git", "push"])
            # git push provides its own feedback, so we just break.
            break
        elif choice == 'n':
            colored_print("Push skipped.\n", "yellow")
            break
        else:
            colored_print("\nInvalid choice. Please enter 'y' or 'n'.\n", "red")

def run_git_command(command: list[str], check: bool = True) -> Optional[str]:
    """
    Executes a Git command as a subprocess and returns its output.
    """
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode != 0 and check:
             colored_print(f"\nError running command '{' '.join(command)}': {result.stderr.strip()}", "red")
             return None
        if result.stdout is None:
            return ""
        return result.stdout.strip()
    except FileNotFoundError:
        colored_print("\nError: 'git' command not found. Is Git installed and in your PATH?", "red")
        return None
    except Exception as e:
        colored_print(f"\nAn unexpected error occurred: {e}", "red")
        return None


# --- 4. CORE LOGIC ---
# The main functions responsible for the script's primary functionality.

def load_master_prompt() -> str:
    """
    Loads the master prompt for the AI.
    It follows a fallback mechanism:
    1. Looks for 'patroMasterPrompt.txt' in the current working directory (project-specific).
    2. If not found, looks for 'default_master_prompt.txt' in the script's directory (global default).
    3. If neither is found, uses a hardcoded fallback prompt.
    
    Returns:
        str: The prompt content to be used for the AI.
    """
    custom_prompt_path = os.path.join(os.getcwd(), 'patroMasterPrompt.txt')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_prompt_path = os.path.join(script_dir, 'default_master_prompt.txt')

    if os.path.exists(custom_prompt_path):
        colored_print("║ Using custom prompt from 'patroMasterPrompt.txt'...\n", "yellow")
        with open(custom_prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif os.path.exists(default_prompt_path):
        colored_print("║ Using default prompt...\n")
        with open(default_prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        colored_print("║ WARNING: No prompt file found. Using hardcoded fallback.\n", "red")
        return """You are an expert programmer writing a commit message.
Your task is to generate a concise and descriptive commit message in English, following the Conventional Commits specification."""

def configure_gemini_model():
    """
    Configures and returns the Gemini GenerativeModel instance using the API key.
    Exits the script if the API key is not found.
    """
    try:
        api_key = os.environ["GEMINI_API_KEY"]
    except KeyError:
        colored_print("Error: GEMINI_API_KEY not found in environment variables.\n", "red")
        sys.exit(1)

    genai.configure(api_key=api_key)
    generation_config = {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 5000}
    # Use the stable model name instead of the 'latest' alias to avoid 404 errors.
    return genai.GenerativeModel(model_name="gemini-2.5-flash-preview-05-20", generation_config=generation_config)

def generate_commit_message(model, master_prompt: str, diff_content: str, additional_message: str) -> Optional[str]:
    """
    Sends the prompt and diff to the Gemini API to generate the commit message.
    """
    context_message = ""
    if additional_message:
        context_message = f"It's important to bear the following in mind: {additional_message}"

    prompt_parts = [
        master_prompt,
        context_message,
        "\n--- GIT DIFF ---\n",
        diff_content,
        "\n--- END OF GIT DIFF ---\n",
        "\nGenerate the commit message now:"
    ]

    try:
        response = model.generate_content(prompt_parts)
        commit_message = response.text.strip().replace("`", "")
        return commit_message
    except Exception as e:
        colored_print(f"\nError generating commit message: {e}\n", color="red")
        return None


# --- 5. MAIN EXECUTION ---
# This is the entry point of the script.

def main():
    """
    Main function to orchestrate the entire git commit workflow.
    """
    colored_print("║ Checking for staged changes...")
    staged_diff = run_git_command(["git", "diff", "--cached"])

    if staged_diff is None:
        sys.exit(1)

    if not staged_diff:
        print() # Add a newline for clean output
        colored_print("No staged changes to commit.", "yellow")
        colored_print(" Do you want to add all files and proceed? (y/n) ", "yellow")
        choice = input().lower()

        if choice in ['y', 's']:
            colored_print("║ Staging all files with 'git add .'...\n", "green")
            run_git_command(["git", "add", "."])
            
            # Re-check for staged changes after adding
            staged_diff = run_git_command(["git", "diff", "--cached"])
            
            if not staged_diff:
                colored_print("Still no changes to commit after 'git add .'. Aborting.\n", "yellow")
                sys.exit(0)
        else:
            colored_print("Aborting. No files were staged.\n", "red")
            sys.exit(0)

    # --- Diff Size Handling ---
    diff_size = len(staged_diff)
    diff_size_kb = diff_size / 1024
    additional_message = sys.argv[1] if len(sys.argv) > 1 else ""

    if diff_size > MAX_DIFF_SIZE:
        # Detailed warning for large diffs
        print() # Add a newline for clean separation
        colored_print(f"Warning: Diff size ({diff_size_kb:.1f} KB) exceeds the limit ({MAX_DIFF_SIZE/1024:.1f} KB).\n", "red")
        colored_print("Trying to use '.gml' files only...\n", "yellow")
        
        staged_diff_gml = run_git_command(["git", "diff", "--cached", "--", "*.gml"])
        if staged_diff_gml and len(staged_diff_gml) <= MAX_DIFF_SIZE:
            staged_diff = staged_diff_gml
            new_size_kb = len(staged_diff) / 1024
            colored_print(f"Using a smaller diff of only .gml files (New size: {new_size_kb:.1f} KB).\n", "yellow")
        else:
            colored_print("The diff is still too large, even with only .gml files.\n", "red")
            colored_print("The diff will be ignored. Please provide a manual summary for the commit.\n", "yellow")
            user_summary = input("Enter a brief summary of your changes: ").strip()
            if not user_summary:
                colored_print("\nA summary is required when the diff is ignored. Aborting.\n", "red")
                sys.exit(1)
            additional_message = user_summary + "\n\nNote: The full diff was ignored due to its large size."
            staged_diff = "" # Clear the diff entirely
    else:
        # Discreet message for normal-sized diffs
        colored_print(f" OK (Size: {diff_size_kb:.1f} KB)\n")

    master_prompt = load_master_prompt()
    
    colored_print("║ Generating commit message with Gemini AI...\n")
    model = configure_gemini_model()
    message = generate_commit_message(model, master_prompt, staged_diff, additional_message)

    if not message:
        sys.exit(1)

    print("---")
    colored_print(message + "\n", "green")
    print("---")

    while True:
        colored_print("Do you want to commit with this message? (y/n/e to edit) ", "yellow")
        choice = input().lower()
        
        if choice in ['y', 's']:
            if run_git_command(["git", "commit", "-m", message]) is not None:
                colored_print("\n✔ Commit created successfully!\n", "green")
                handle_push()
            break
        elif choice == 'e':
            if run_git_command(["git", "commit", "-m", message, "--edit"]) is not None:
                colored_print("\n✔ Commit edited and created successfully!\n", "green")
                handle_push()
            break
        elif choice == 'n':
            colored_print("\nCommit aborted by user.\n", "red")
            break
        else:
            colored_print("\nInvalid choice. Please enter 'y', 'n', or 'e'.\n", "red")

if __name__ == "__main__":
    if run_git_command(["git", "rev-parse", "--is-inside-work-tree"], check=False) != "true":
        colored_print("Error: This is not a git repository.\n", "red")
        sys.exit(1)
    # If it is a repo, run the main function.
    main()

