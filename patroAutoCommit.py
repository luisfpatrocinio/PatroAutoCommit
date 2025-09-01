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
            encoding="utf-8",  # Adicionado para evitar problemas de decodificação
            errors="replace"   # Substitui caracteres inválidos por �
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
    # Path for the custom prompt in the project's folder (Current Working Directory)
    custom_prompt_path = os.path.join(os.getcwd(), 'patroMasterPrompt.txt')
    
    # Path for the default prompt located next to this script
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
        # This is a safe fallback in case the default prompt file is deleted.
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
    return genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=generation_config)

def generate_commit_message(model, master_prompt: str, diff_content: str, additional_message: str) -> Optional[str]:
    """
    Sends the prompt and diff to the Gemini API to generate the commit message.
    
    Args:
        model: The configured Gemini model instance.
        master_prompt (str): The main instruction prompt for the AI.
        diff_content (str): The git diff of staged changes.
        additional_message (str): Optional user-provided context.
        
    Returns:
        Optional[str]: The generated commit message, or None on error.
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
        # Clean up the response, removing backticks and extra whitespace.
        commit_message = response.text.strip().replace("`", "")
        return commit_message
    except Exception as e:
        colored_print(f"\nError generating commit message: {e}\n", color="red")
        return None


# --- 5. MAIN EXECUTION ---
# This is the entry point of the script.

def main():
    """
    Main function to orchestrate the entire git commit workflow:
    1. Checks for staged files.
    2. Loads the appropriate AI prompt.
    3. Generates the commit message.
    4. Interacts with the user to confirm, edit, or abort the commit.
    """
    colored_print("║ Checking for staged changes...\n")
    staged_diff = run_git_command(["git", "diff", "--cached"])

    if staged_diff is None: # An error occurred while running git command
        sys.exit(1)
    if not staged_diff:
        colored_print("No staged changes to commit. Use 'git add <files>' first.\n", "yellow")
        sys.exit(0)

    MAX_DIFF_SIZE = 20000  # Limite de caracteres para o diff

    if len(staged_diff) > MAX_DIFF_SIZE:
        colored_print("O diff está muito grande! Tentando considerar apenas arquivos '.gml'...\n", "yellow")
        staged_diff_gml = run_git_command(["git", "diff", "--cached", "--", "*.gml"])
        if staged_diff_gml and len(staged_diff_gml) <= MAX_DIFF_SIZE:
            staged_diff = staged_diff_gml
        else:
            colored_print("Mesmo considerando apenas arquivos '.gml', o diff está muito grande.\n", "red")
            colored_print("Você pode digitar um contexto para o commit, e o diff será ignorado.\n", "yellow")
            user_prompt = input("Digite um contexto para o commit (em inglês): ").strip()
            # Adiciona observação ao prompt
            user_prompt += "\n\nNote: The diff was ignored due to its large size and is not included in this commit message."
            staged_diff = ""  # Ignora o diff
            additional_message = user_prompt

    # The first command-line argument is treated as an optional context message.
    additional_message = sys.argv[1] if len(sys.argv) > 1 else ""
    
    # Load the prompt from file (or fallback).
    master_prompt = load_master_prompt()
    
    # Generate the commit message.
    colored_print("║ Generating commit message with Gemini AI...\n")
    model = configure_gemini_model()
    message = generate_commit_message(model, master_prompt, staged_diff, additional_message)

    if not message:
        sys.exit(1) # Exit if message generation failed.

    # Display the generated message to the user.
    print("---")
    colored_print(message + "\n", "green")
    print("---")

    # Start the interactive loop for user confirmation.
    while True:
        colored_print("Do you want to commit with this message? (y/n/e to edit) ", "yellow")
        choice = input().lower()
        
        if choice == 'y':
            run_git_command(["git", "commit", "-m", message])
            colored_print("\n✔ Commit created successfully!\n", "green")
            break
        elif choice == 'e':
            # The '--edit' flag opens the user's default text editor.
            run_git_command(["git", "commit", "-m", message, "--edit"])
            colored_print("\n✔ Commit edited and created successfully!\n", "green")
            break
        elif choice == 'n':
            colored_print("\nCommit aborted by user.\n", "red")
            break
        else:
            colored_print("Invalid choice. Please enter 'y', 'n', or 'e'.\n", "red")

# The script execution starts here.
if __name__ == "__main__":
    # First, verify that the current directory is a Git repository.
    if run_git_command(["git", "rev-parse", "--is-inside-work-tree"], check=False) != "true":
        colored_print("Error: This is not a git repository.\n", "red")
        sys.exit(1)
    # If it is a repo, run the main function.
    main()
