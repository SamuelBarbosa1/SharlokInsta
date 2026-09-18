import time
from datetime import datetime, timedelta
from .monitor import fluxo_verificar_e_baixar

def modo_sentinela():
    """Executa checagens periódicas automáticas de alvos e cascata sem intervenção manual."""
    print("\n" + "╔" + "═"*62 + "╗")
    print("║                 👁️ MODO SENTINELA ATIVO (24/7)              ║")
    print("║     Monitoramento Contínuo, Cascata e Download Automático    ║")
    print("╚" + "═"*62 + "╝")

    intervalo_input = input(">> Intervalo entre checagens em minutos (Padrão 30): ").strip()
    intervalo_min = int(intervalo_input) if intervalo_input.isdigit() and int(intervalo_input) > 0 else 30
    intervalo_seg = intervalo_min * 60

    print(f"\n[*] Modo Sentinela iniciado! Intervalo de checagem: {intervalo_min} minutos.")
    print("[*] Pressione Ctrl + C a qualquer momento para pausar e voltar ao menu principal.\n")

    ciclo = 1
    try:
        while True:
            agora_str = datetime.now().strftime("%H:%M:%S")
            print("="*65)
            print(f"[{agora_str}] [Ciclo #{ciclo}] Executando verificação de alvos...")
            print("="*65)

            try:
                fluxo_verificar_e_baixar()
            except Exception as e:
                print(f"[-] Ocorreu um erro durante a verificação no ciclo #{ciclo}: {e}")

            proxima_hora = (datetime.now() + timedelta(seconds=intervalo_seg)).strftime("%H:%M:%S")
            print(f"\n[💤] Ciclo #{ciclo} concluído. Próxima checagem automática às {proxima_hora}...")

            # Aguarda o intervalo dormindo em passos de 1s para responder de imediato ao Ctrl+C
            for _ in range(intervalo_seg):
                time.sleep(1)

            ciclo += 1
    except KeyboardInterrupt:
        print("\n\n[i] Modo Sentinela pausado pelo usuário. Retornando ao menu principal...\n")
        time.sleep(1)
