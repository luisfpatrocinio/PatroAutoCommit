# PatroAutoCommit 🚀

A simple yet powerful tool that uses the Google Gemini AI to automatically generate descriptive and conventional commit messages from your staged changes.

## About The Project

Tired of spending time thinking about the perfect commit message? This project automates that process. It reads your staged code differences (`git diff`), sends them to the Gemini API with a carefully crafted prompt, and returns a commit message that follows the **Conventional Commits** specification.

The workflow is handled by a simple shell script (`gcommit.sh`) that makes the process seamless right from your terminal.

---

## Features ✨

- **AI-Powered Messages**: Leverages Google Gemini for high-quality, context-aware commit messages.
- **Conventional Commits**: Enforces a structured commit history, making it easier to understand changes and automate releases.
- **Interactive Workflow**: The script allows you to **accept**, **edit**, or **reject** the generated message before committing.
- **Easy Setup**: Requires minimal configuration to get started.

---

## Getting Started

Follow these steps to set up the project locally.

### Prerequisites

- **Git** installed on your system.
- **Python 3.6+** and **Pip**.
- A **Google Gemini API Key**. You can get one for free at [Google AI Studio](https://aistudio.google.com/app/apikey).

### Installation

1.  **Clone the repository:**

    ```sh
    git clone [https://github.com/your-username/PatroAutoCommit.git](https://github.com/your-username/PatroAutoCommit.git)
    cd PatroAutoCommit
    ```

2.  **Install Python dependencies:**

    ```sh
    pip install google-generativeai python-dotenv pyperclip
    ```

3.  **Set up your environment variables:**
    This project requires a Gemini API key. We use a `.env.example` file to show you which variables are needed.

    First, copy the example file to a new file named `.env`:

    ```sh
    # For Linux/macOS
    cp .env.example .env

    # For Windows (Command Prompt)
    # copy .env.example .env
    ```

    Next, open the new `.env` file and add your personal Gemini API key:

    ```
    GEMINI_API_KEY="PASTE_YOUR_API_KEY_HERE"
    ```

    This `.env` file is already listed in `.gitignore`, so your key will remain private.

4.  **Make the script executable:**
    ```sh
    chmod +x gcommit.sh
    ```

---

## Usage 💡

Using the tool is straightforward:

1.  **Stage your changes** as you normally would:

    ```sh
    git add .
    # or
    git add <file1> <file2>
    ```

2.  **Run the script:**

    ```sh
    ./gcommit.sh
    ```

3.  The script will generate a message and prompt you for action:
    - Press **`y`** to commit with the generated message.
    - Press **`e`** to open your default text editor to edit the message before committing.
    - Press any other key to cancel the commit.

That's it! Your commit will be created with a clean, AI-generated message.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Contact

Luis Felipe Patrocinio - [GitHub](https://github.com/luisfpatrocinio)
