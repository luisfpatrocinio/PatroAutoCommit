import subprocess
import os
import pyperclip
import sys
import json
from datetime import datetime, timedelta
# Importação da biblioteca Gemini API
import google.generativeai as genai
from typing import Optional # Para tipagem opcional
import time # Adicionado para a lógica de retentativa

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

# --- CONFIGURAÇÃO GLOBAL DE CORES (ANSI) ---
# Mapeia cores semânticas para códigos ANSI para saída no console.
ANSI_COLORS = {
    "SUCCESS": "\033[92m", # Verde Claro
    "ERROR": "\033[91m",   # Vermelho Claro
    "WARNING": "\033[93m", # Amarelo Claro
    "HEADER": "\033[94m",  # Azul Claro
    "RESET": "\033[0m"
}
# Dicionário global que armazenará as cores Hex carregadas do settings.json
APP_COLORS = {}

def colorize_text(text: str, color_name: str) -> str:
    """
    Aplica códigos ANSI ao texto para colorir a saída no console, 
    usando as chaves de cores semânticas (SUCCESS, ERROR, etc.).
    """
    # Note: O código usa o nome semântico para pegar o código ANSI correspondente,
    # ignorando o valor Hex no APP_COLORS, pois terminais não suportam todos os HEX.
    color_code = ANSI_COLORS.get(color_name.upper(), ANSI_COLORS["RESET"])
    return f"{color_code}{text}{ANSI_COLORS['RESET']}"

# --- CONFIGURAÇÃO GLOBAL ---
# Define o diretório do script e o caminho completo para o arquivo de debug.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_PROMPT_FILENAME = "last_prompt_for_debug.txt"
DEBUG_PROMPT_FILE = os.path.join(SCRIPT_DIR, DEBUG_PROMPT_FILENAME)

DEFAULT_SETTINGS = {
    "show_hashes": True,
    "colors": {
        "success_hex": "#2ecc71", # Verde para sucesso
        "error_hex": "#e74c3c",   # Vermelho para erros
        "warning_hex": "#f1c40f", # Amarelo para avisos
        "header_hex": "#3498db"   # Azul para cabeçalhos/info
    }
}
# --------------------------

# --- Constante de Instrução do Sistema (Definida globalmente para uso na configuração) ---
SYSTEM_INSTRUCTION_REPORT = (
    "Você é um assistente de Daily Report de desenvolvimento de jogos. "
    "Sua tarefa é analisar as mensagens de commit brutas, o foco planejado e os bloqueios, "
    "e gerar um Daily Report conciso em Português, seguindo o formato padrão fornecido. "
    "Resuma os avanços em uma única linha (máximo 150 caracteres), mantendo a objetividade e "
    "**EVITANDO QUALQUER EMOJI no texto do resumo e nos itens de Foco/Bloqueio**."
    "O formato de saída DEVE ser estritamente o seguinte, usando APENAS os emojis indicados nos cabeçalhos, sem introdução ou conclusão adicionais: "
    ":white_check_mark: **Avanços:** [Resumo em uma linha]\n"
    ":pencil: **Foco:** [Lista de itens do foco, iniciando com '*']\n"
    ":warning: **Bloqueio:** [Problemas ou N/A]"
)
# -------------------------------------------------------------------------------------


def load_settings():
    """
    Carrega as configurações do arquivo settings.json. Se não existir, cria um.
    """
    global APP_COLORS

    if not os.path.exists(SETTINGS_FILE):
        print(colorize_text("Arquivo de configurações não encontrado. Criando um novo com as configurações padrão.", "WARNING"))
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        print(colorize_text("Arquivo 'settings.json' criado com sucesso.", "SUCCESS"))
    else:
        print(colorize_text("Configurações lidas com sucesso do arquivo 'settings.json'.", "SUCCESS"))
    
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    # Armazena as cores Hex carregadas (apenas para documentação/referência)
    APP_COLORS.update(settings.get("colors", DEFAULT_SETTINGS["colors"]))

    return settings

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
        print(colorize_text(f"Erro ao buscar o commit {commit_hash}: {e.stderr.strip()}", "ERROR"), file=sys.stderr)
        return None
    except FileNotFoundError:
        print(colorize_text("Erro: O comando 'git' não foi encontrado. Certifique-se de que o Git está instalado e no seu PATH.", "ERROR"), file=sys.stderr)
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
        print(colorize_text("Detectado Segunda-feira: Buscando commits dos últimos 3 dias úteis (Sexta, Sábado, Domingo) + Hoje.", "HEADER")) 
    else:
        # Terça a sexta: retrocede 1 dia (para incluir ontem)
        days_to_look_back = 1
        print(colorize_text("Buscando commits de ontem e hoje.", "HEADER"))

    # Calcula a data de início (início do dia 'days_to_look_back' atrás)
    since_date_dt = today - timedelta(days=days_to_look_back)
    
    # Formato de data para o Git (YYYY-MM-DD)
    since_date = since_date_dt.strftime('%Y-%m-%d')
    until_date = (today + timedelta(days=1)).strftime('%Y-%m-%d') # Vai até o final de hoje
    
    
    print(colorize_text(f"Filtrando commits desde {since_date} (exclusivo) até {today.strftime('%Y-%m-%d')} (inclusivo)...", "HEADER"))

    try:
        # --since e --until são usados para restringir o período
        command = ['git', 'log', 
            f'--since={since_date}', 
            f'--until={until_date}',
            '--pretty=format:%H'
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        hashes = result.stdout.strip().split('\n')
        
        # Filtra hashes vazios que podem surgir se não houver commits
        valid_hashes = [h for h in hashes if h]
        
        if not valid_hashes:
            print(colorize_text("Nenhum commit encontrado no período especificado.", "WARNING"))
            return None

        return compile_messages(valid_hashes, show_hashes)

    except subprocess.CalledProcessError as e:
        print(colorize_text(f"Erro ao obter commits por data: {e.stderr}", "ERROR"), file=sys.stderr)
        return None


def configure_gemini_model() -> Optional[genai.GenerativeModel]:
    """
    Configura e retorna a instância do modelo GenerativeModel do Gemini.
    """
    global API_KEY
    if not API_KEY:
        print(colorize_text("Erro: A variável de ambiente GEMINI_API_KEY não foi encontrada.", "ERROR"), file=sys.stderr)
        print(colorize_text("Por favor, configure-a para usar o modo de Daily Report automático.", "ERROR"))
        return None

    try:
        genai.configure(api_key=API_KEY)
        
        # Configuração do modelo: Temperatura mais baixa e mais tokens para estabilidade
        config = {
            "temperature": 0.1,  # Mais focado na instrução e menos criativo (mais estável)
            "max_output_tokens": 2048 # Aumentado para dar margem de processamento
        }
        
        # Usando gemini-2.5-flash
        return genai.GenerativeModel(model_name="gemini-2.5-flash", generation_config=config)
    except Exception as e:
        print(colorize_text(f"Erro ao configurar o modelo Gemini: {e}", "ERROR"), file=sys.stderr)
        return None

def generate_daily_report(model: genai.GenerativeModel, raw_commits: str, custom_advances: str = "", focus: str = "", blocks: str = "") -> Optional[str]:
    """
    Gera o Daily Report resumido usando o Gemini AI em um único envio.
    A instrução do sistema é enviada como parte do prompt do usuário.
    """
    
    # --- Formatação dos Avanços ---
    all_advances_input = raw_commits
    if custom_advances.strip():
        all_advances_input += f"\n--- AVANÇOS MANUAIS ADICIONAIS ---\n{custom_advances}\n"
    
    # Verifica e formata os itens de Foco e Bloqueio em listas
    if focus:
        focus_list = "\n".join([f"* {item.strip()}" for item in focus.split(',') if item.strip()])
    else:
        focus_list = "* N/A"
        
    # Define o texto de Bloqueios.
    blocks_text = "N/A" if blocks.lower().strip() in ('n/a', 'nenhum', '') else blocks

    # Prepara o prompt, garantindo que o modelo saiba sua função e formato
    user_prompt = (
        f"{SYSTEM_INSTRUCTION_REPORT}\n\n"
        f"Gere um Daily Report de equipe com base nas seguintes informações:\n\n"
        f"--- MENSAGENS DE COMMIT E AVANÇOS ---\n{all_advances_input}\n"
        f"--- FOCO PLANEJADO PARA HOJE ---\n{focus_list}\n\n"
        f"--- BLOQUEIOS / PROBLEMAS ---\n{blocks_text}\n\n"
        f"Gere o relatório agora, seguindo estritamente o formato de três pontos (Avanços, Foco, Bloqueio) e a instrução do sistema."
    )

    try:
        print(colorize_text("\nGerando Daily Report com Gemini AI...", "HEADER"))
        
        # --- Aviso de Tamanho do Prompt ---
        prompt_size = len(user_prompt.encode('utf-8'))
        print(f"Tamanho do Prompt (em bytes): {prompt_size}")
        # -------------------------------------

        # --- Salva o prompt para depuração antes de chamar a API ---
        try:
            with open(DEBUG_PROMPT_FILE, "w", encoding='utf-8') as f:
                f.write(user_prompt)
            print(colorize_text(f"✔ Prompt salvo em '{DEBUG_PROMPT_FILENAME}' para depuração.", "SUCCESS"))
        except Exception as e:
            print(colorize_text(f"Erro ao salvar prompt de depuração: {e}", "ERROR"), file=sys.stderr)
        # -----------------------------------------------------------------
        
        # --- Lógica de Único Envio ---
        response = model.generate_content(
            contents=user_prompt
        )
        
        # Verifica a validade da resposta ANTES de acessar response.text
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            # Sucesso: Extrai o texto
            text = response.text.strip()
            
            # Substitui os marcadores de emoji no output para o emoji real para exibição/cópia
            text = text.replace(":white_check_mark:", "✅")
            text = text.replace(":pencil:", "📝")
            text = text.replace(":warning:", "⚠️")
            return text
        else:
            # Falha na geração (finish_reason)
            finish_reason = response.candidates[0].finish_reason if response.candidates and response.candidates[0].finish_reason else "UNKNOWN"
            error_message = f"Geração falhou (Finish Reason: {finish_reason}). Verifique o arquivo '{DEBUG_PROMPT_FILENAME}'."
            
            # Se a falha for de segurança (FINISH_REASON_SAFETY), adiciona mensagem
            if finish_reason == 2: # 2 = FINISH_REASON_SAFETY
                error_message += " Causa provável: O conteúdo do prompt violou as políticas de segurança."
                
            raise Exception(error_message)

    except Exception as e:
        print(colorize_text(f"\nErro na chamada da API Gemini: {e}", "ERROR"), file=sys.stderr)
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
        print(colorize_text("Ajuste a sua API Key e tente novamente.", "ERROR"))
        return

    # Sempre pega o raw para análise da IA (com hashes)
    raw_commits = get_commits_by_date_range(show_hashes=True) 
    
    if not raw_commits:
        print(colorize_text("Nenhum commit encontrado no período para gerar o relatório.", "WARNING"), file=sys.stderr)
        # Permite continuar mesmo sem commits, se houver avanços manuais
    
    # ----------------------------------------------------------------------
    # 2. Coletar Foco, Bloqueios e Avanços Manuais
    # ----------------------------------------------------------------------
    print(colorize_text("\n--- INFORMAÇÕES ADICIONAIS PARA O RELATÓRIO ---", "HEADER"))
    custom_advances = input("Avanços feitos que NÃO ESTÃO nos commits (ou deixe vazio): ").strip()
    focus = input("Foco planejado para hoje (separado por vírgulas, ex: 'corrigir bug X, iniciar feature Y'): ").strip()
    blocks = input("Bloqueios ou problemas (N/A se não houver): ").strip()
    
    # Se não houver commits NEM avanços manuais, encerra
    if not raw_commits and not custom_advances:
        print(colorize_text("\nNenhum avanço (commits ou manual) para gerar o relatório. Encerrando.", "WARNING"), file=sys.stderr)
        return
        
    # ----------------------------------------------------------------------
    # 3. Gerar Relatório via Gemini AI
    # ----------------------------------------------------------------------
    report = generate_daily_report(model, raw_commits, custom_advances, focus, blocks)
    
    if not report:
        print(colorize_text("Não foi possível gerar o relatório. Encerrando.", "ERROR"), file=sys.stderr)
        return

    # Compila o texto final (SEM o cabeçalho no corpo do texto)
    compiled_text_body = report
    output_filename = "daily_report.txt"
    
    # Cabeçalho completo para exibição/cópia
    full_report_text = "@everyone 🚀 Hora do Daily Report! 🚀\n\n" + compiled_text_body


    # ----------------------------------------------------------------------
    # 4. Exibir, Perguntar para Edição e Salvar
    # ----------------------------------------------------------------------
    print(colorize_text("\n" + "="*70, "HEADER"))
    print(colorize_text("DAILY REPORT GERADO:", "HEADER"))
    print(colorize_text("="*70, "HEADER"))
    print(compiled_text_body) # Exibe APENAS o corpo
    print(colorize_text("="*70, "HEADER"))
    
    
    # Salva o arquivo temporariamente para edição (usa o texto COMPLETO)
    with open(output_filename, "w", encoding='utf-8') as f:
        f.write(full_report_text)

    # Copia o texto COMPLETO para a área de transferência
    try:
        pyperclip.copy(full_report_text)
        print(colorize_text("\n✔ Sucesso! O relatório foi copiado para a área de transferência.", "SUCCESS"))
    except pyperclip.PyperclipException as e:
        print(colorize_text(f"\n! Aviso: Não foi possível copiar para a área de transferência. Erro: {e}", "WARNING"), file=sys.stderr)
    
    # Pergunta sobre edição
    save_choice = input("Deseja salvar o relatório em arquivo? (s/n): ").strip().lower()

    if save_choice == 's':
        edit_choice = input("Deseja editar o relatório antes de salvar permanentemente? (s/n): ").strip().lower()
        
        if edit_choice == 's':
            try:
                # Tenta abrir o arquivo no editor de texto padrão
                if sys.platform == "win32":
                    os.system(f'notepad "{output_filename}"')
                elif sys.platform == "darwin":
                    os.system(f'open -e "{output_filename}"') # Para macOS
                else:
                    os.system(f'nano "{output_filename}"') # Para Linux/Outros
                    
                # Recarrega o conteúdo após a edição para salvar
                with open(output_filename, 'r', encoding='utf-8') as f:
                    # Este texto (final_text) é o que foi editado/salvo pelo usuário.
                    final_text = f.read()
                
                print(colorize_text(f"\n✔ Relatório editado e salvo permanentemente em '{output_filename}'.", "SUCCESS"))
                    
            except Exception as e:
                print(colorize_text(f"\n! Erro ao abrir o editor. O arquivo foi salvo em '{output_filename}'. Erro: {e}", "ERROR"), file=sys.stderr)
        else:
             # Já está salvo com o texto original da IA no passo anterior
             print(colorize_text(f"\n✔ Relatório salvo permanentemente em '{output_filename}'.", "SUCCESS"))

    else:
        # Se não quiser salvar, remove o arquivo temporário
        if os.path.exists(output_filename):
            os.remove(output_filename)
            print(colorize_text("\nRelatório não salvo em arquivo.", "WARNING"))


if __name__ == "__main__":
    main()
