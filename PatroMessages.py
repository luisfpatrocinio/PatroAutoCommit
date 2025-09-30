import subprocess
import os
import pyperclip
import sys
import json
from datetime import datetime, timedelta
# Importação da biblioteca Gemini API
import google.generativeai as genai
from typing import Optional # Para tipagem opcional

# --- Adicionado: Importação e carregamento de .env ---
try:
    # Tenta carregar variáveis de ambiente do .env
    from dotenv import load_dotenv
    load_dotenv() # Carrega variáveis do arquivo .env na pasta do script/execução
except ImportError:
    print("Aviso: A biblioteca 'python-dotenv' não está instalada. A chave API será buscada apenas nas variáveis de ambiente do sistema.")
# ----------------------------------------------------


# Variável de ambiente para a chave da API (o usuário deve configurar isso)
# Em um ambiente real, o usuário deve garantir que GEMINI_API_KEY esteja configurada.
API_KEY = os.environ.get("GEMINI_API_KEY", "")


SETTINGS_FILE = 'settings.json'
DEFAULT_SETTINGS = {
    "show_hashes": True
}

# --- Constante de Instrução do Sistema (Definida globalmente para uso na configuração) ---
SYSTEM_INSTRUCTION_REPORT = (
    "Você é um assistente de Daily Report de desenvolvimento de jogos. "
    "Sua tarefa é analisar as mensagens de commit brutas, o foco planejado e os bloqueios, "
    "e gerar um Daily Report conciso em Português, seguindo o formato padrão fornecido. "
    "Resuma os avanços em uma única linha (máximo 150 caracteres), mantendo a objetividade e usando emojis. "
    "O formato de saída DEVE ser estritamente o seguinte, sem introdução ou conclusão adicionais: "
    ":white_check_mark: **Avanços:** [Resumo em uma linha]\n"
    ":pencil: **Foco:** [Lista de itens do foco, iniciando com '*']\n"
    ":warning: **Bloqueio:** [Problemas ou N/A]"
)
# -------------------------------------------------------------------------------------


def load_settings():
    """
    Carrega as configurações do arquivo settings.json. Se não existir, cria um.
    """
    if not os.path.exists(SETTINGS_FILE):
        print("Arquivo de configurações não encontrado. Criando um novo com as configurações padrão.")
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        print("Arquivo 'settings.json' criado com sucesso.")
    else:
        print("Configurações lidas com sucesso do arquivo 'settings.json'.")
    
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_commit_message(commit_hash):
    """
    Busca a mensagem completa de um commit a partir do seu hash usando o comando git.
    """
    try:
        command = ['git', 'show', '--no-patch', '--no-notes', '--pretty=format:%B', commit_hash]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Erro comum se o script não estiver no repositório ou o hash for inválido
        print(f"Erro ao buscar o commit {commit_hash}: {e.stderr.strip()}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("Erro: O comando 'git' não foi encontrado. Certifique-se de que o Git está instalado e no seu PATH.", file=sys.stderr)
        return None

def get_commit_timestamp(commit_hash):
    """
    Busca o timestamp de um commit a partir do seu hash.
    """
    try:
        # O formato %ad com --date=format... retorna a data do autor, formatada.
        command = ['git', 'show', '--no-patch', '--no-notes', '--pretty=format:%ad', '--date=format:%Y-%m-%d %H:%M:%S', commit_hash]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        return None

def format_message(commit_hash, timestamp, message, show_hashes):
    """
    Formata a mensagem de commit com base nas configurações.
    """
    output = ""
    if show_hashes:
        output += f"Commit Hash: {commit_hash}\n"
    output += f"Timestamp: {timestamp}\n"
    output += f"{message}\n"
    output += "-"*50 + "\n"
    return output

def compile_messages(hashes, show_hashes):
    """
    Compila as mensagens, timestamps e hashes em uma única string formatada.
    """
    messages = []
    for h in hashes:
        msg = get_commit_message(h)
        timestamp = get_commit_timestamp(h)
        if msg and timestamp:
            messages.append(format_message(h, timestamp, msg, show_hashes))
    return "".join(messages)

def get_commits_by_date_range(show_hashes):
    """
    Busca commits do período necessário:
    - Segunda-feira (dia 0): Pega 3 dias (Sex, Sáb, Dom) + Hoje. Total de 4 dias no filtro para incluir as 72h + commits de segunda.
    - Outros dias: Pega 2 dias (Hoje e Ontem).
    """
    today = datetime.now()
    
    # 0 = Segunda-feira, 6 = Domingo
    if today.weekday() == 0:  
        # Segunda-feira: retrocede 3 dias (para incluir sexta)
        days_to_look_back = 3
        print("Detectado Segunda-feira: Buscando commits dos últimos 3 dias úteis (Sexta, Sábado, Domingo) + Hoje.") 
    else:
        # Terça a sexta: retrocede 1 dia (para incluir ontem)
        days_to_look_back = 1
        print("Buscando commits de ontem e hoje.")

    # Calcula a data de início (início do dia 'days_to_look_back' atrás)
    since_date_dt = today - timedelta(days=days_to_look_back)
    
    # Formato de data para o Git (YYYY-MM-DD)
    since_date = since_date_dt.strftime('%Y-%m-%d')
    until_date = (today + timedelta(days=1)).strftime('%Y-%m-%d') # Vai até o final de hoje
    
    
    print(f"Filtrando commits desde {since_date} (exclusivo) até {today.strftime('%Y-%m-%d')} (inclusivo)...")

    try:
        # --since e --until são usados para restringir o período
        command = [
            'git', 'log', 
            f'--since={since_date}', 
            f'--until={until_date}',
            '--pretty=format:%H'
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        hashes = result.stdout.strip().split('\n')
        
        # Filtra hashes vazios que podem surgir se não houver commits
        valid_hashes = [h for h in hashes if h]
        
        if not valid_hashes:
            print("Nenhum commit encontrado no período especificado.")
            return None

        return compile_messages(valid_hashes, show_hashes)

    except subprocess.CalledProcessError as e:
        print(f"Erro ao obter commits por data: {e.stderr}", file=sys.stderr)
        return None


def configure_gemini_model() -> Optional[genai.GenerativeModel]:
    """
    Configura e retorna a instância do modelo GenerativeModel do Gemini.
    """
    global API_KEY
    if not API_KEY:
        print("Erro: A variável de ambiente GEMINI_API_KEY não foi encontrada.", file=sys.stderr)
        print("Por favor, configure-a para usar o modo de Daily Report automático.")
        return None

    try:
        genai.configure(api_key=API_KEY)
        
        # Configuração do modelo
        config = {
            "temperature": 0.3, 
            "max_output_tokens": 1000
        }
        
        # O modelo 'gemini-1.5-flash-latest' é o mais recomendado para tarefas de summarização.
        return genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=config)
    except Exception as e:
        print(f"Erro ao configurar o modelo Gemini: {e}", file=sys.stderr)
        return None

def generate_daily_report(model: genai.GenerativeModel, raw_commits: str, focus: str = "", blocks: str = "") -> Optional[str]:
    """
    Gera o Daily Report resumido usando o Gemini AI.
    A instrução do sistema é enviada como parte do prompt do usuário.
    """
    
    # Verifica e formata os itens de Foco e Bloqueio em listas
    # Certifica-se de que os itens de foco são formatados com um asterisco por linha, se múltiplos.
    if focus:
        focus_list = "\n".join([f"* {item.strip()}" for item in focus.split(',') if item.strip()])
    else:
        focus_list = "* N/A"
        
    blocks_text = blocks if blocks.lower() not in ('n/a', 'nenhum', '') else "Nenhum no momento."

    # Prepara o prompt, garantindo que o modelo saiba sua função e formato
    user_prompt = (
        f"{SYSTEM_INSTRUCTION_REPORT}\n\n" # Inclui a instrução do sistema diretamente no prompt.
        f"Gere um Daily Report de equipe com base nas seguintes informações:\n\n"
        f"--- MENSAGENS DE COMMIT (AVANÇOS) ---\n{raw_commits}\n\n"
        f"--- FOCO PLANEJADO PARA HOJE ---\n{focus_list}\n\n"
        f"--- BLOQUEIOS / PROBLEMAS ---\n{blocks_text}\n\n"
        f"Gere o relatório agora, seguindo estritamente o formato de três pontos (Avanços, Foco, Bloqueio) e a instrução do sistema."
    )

    try:
        print("\nGerando Daily Report com Gemini AI...")
        # Chamada simples, confiando que a instrução do sistema está no contents.
        response = model.generate_content(
            contents=user_prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"\nErro na chamada da API Gemini: {e}", file=sys.stderr)
        return None

def main():
    """
    Função principal para gerar o Daily Report automático.
    """
    settings = load_settings()
    show_hashes = settings.get("show_hashes", True)
    
    # ----------------------------------------------------------------------
    # 1. Obter Commits (Automático - 2 ou 3 dias)
    # ----------------------------------------------------------------------
    model = configure_gemini_model()
    if not model:
        print("Ajuste a sua API Key e tente novamente.")
        return

    # Sempre pega o raw para análise da IA (com hashes)
    raw_commits = get_commits_by_date_range(show_hashes=True) 
    
    if not raw_commits:
        print("Nenhum commit encontrado no período para gerar o relatório.", file=sys.stderr)
        return

    # ----------------------------------------------------------------------
    # 2. Coletar Foco e Bloqueios
    # ----------------------------------------------------------------------
    print("\n--- INFORMAÇÕES ADICIONAIS PARA O RELATÓRIO ---")
    focus = input("Foco planejado para hoje (separado por vírgulas, ex: 'corrigir bug X, iniciar feature Y'): ").strip()
    blocks = input("Bloqueios ou problemas (N/A se não houver): ").strip()
    
    # ----------------------------------------------------------------------
    # 3. Gerar Relatório via Gemini AI
    # ----------------------------------------------------------------------
    report = generate_daily_report(model, raw_commits, focus, blocks)
    
    if not report:
        print("Não foi possível gerar o relatório. Encerrando.", file=sys.stderr)
        return

    # Compila o texto final (SEM o cabeçalho no corpo do texto)
    compiled_text_body = report
    output_filename = "daily_report.txt"
    
    # Cabeçalho completo para exibição/cópia
    full_report_text = "@everyone 🚀 Hora do Daily Report! 🚀\n\n" + compiled_text_body


    # ----------------------------------------------------------------------
    # 4. Exibir, Perguntar para Edição e Salvar
    # ----------------------------------------------------------------------
    print("\n" + "="*70)
    print("DAILY REPORT GERADO:")
    print("="*70)
    print(compiled_text_body) # Exibe APENAS o corpo
    print("="*70)
    
    
    # Salva o arquivo temporariamente para edição (usa o texto COMPLETO)
    with open(output_filename, "w", encoding='utf-8') as f:
        f.write(full_report_text)

    # Copia o texto COMPLETO para a área de transferência
    try:
        pyperclip.copy(full_report_text)
        print("\n✔ Sucesso! O relatório foi copiado para a área de transferência.")
    except pyperclip.PyperclipException as e:
        print(f"\n! Aviso: Não foi possível copiar para a área de transferência. Erro: {e}", file=sys.stderr)
    
    # Pergunta sobre edição
    edit_choice = input("Deseja editar o relatório (abrir no bloco de notas) e salvar em arquivo? (s/n): ").strip().lower()

    if edit_choice == 's':
        try:
            # Tenta abrir o arquivo no editor de texto padrão
            if sys.platform == "win32":
                os.system(f'notepad "{output_filename}"')
            elif sys.platform == "darwin":
                os.system(f'open -e "{output_filename}"') # Para macOS
            else:
                os.system(f'nano "{output_filename}"') # Para Linux/Outros
                
            # Recarrega o conteúdo após a edição
            with open(output_filename, 'r', encoding='utf-8') as f:
                final_text = f.read()
            
            # Não precisa copiar de novo se o usuário abriu para editar, mas confirma o salvamento
            print(f"\n✔ Relatório editado e salvo em '{output_filename}'.")
                
        except Exception as e:
            print(f"\n! Erro ao abrir o editor. O arquivo foi salvo em '{output_filename}'. Erro: {e}", file=sys.stderr)
    else:
        print(f"\nRelatório não editado. O texto completo (com cabeçalho) foi salvo em '{output_filename}'.")


if __name__ == "__main__":
    main()
