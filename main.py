import sys
from core.database import inicializar_banco
from core.pool import carregar_pool_contas
from flows.follow import fluxo_seguir_alvo
from flows.monitor import fluxo_verificar_e_baixar
from flows.direct import fluxo_baixar_direto
from flows.history import fluxo_historico
from flows.pool_menu import fluxo_gerenciar_pool
from flows.sentinel import modo_sentinela

# Força UTF-8 no console Windows para evitar UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    """Menu principal do SharlokInsta Desktop Automation."""
    inicializar_banco()
    carregar_pool_contas()

    while True:
        print("\n" + "╔" + "═"*58 + "╗")
        print("║       🕵️‍♂️ SHARLOK INSTA - DESKTOP AUTOMATION (PC)         ║")
        print("║       Multi-Contas, Cascata & Monitoramento Sentinela    ║")
        print("╚" + "═"*58 + "╝")
        print(" [1] 🎯 Enviar Solicitação para Alvo Privado & Monitorar")
        print(" [2] 🔄 Verificar Solicitações & Cascata de Rejeição")
        print(" [3] ⚡ Baixar Perfil Agora (Alvos Já Aceitos ou Públicos)")
        print(" [4] 📋 Ver Histórico de Alvos e Status da Cascata")
        print(" [5] 👥 Gerenciar Pool de Contas (Adicionar Conta 2, Listar)")
        print(" [6] 👁️ Iniciar Modo Sentinela (Loop Automático 24/7)")
        print(" [0] 🚪 Sair")

        try:
            escolha = input("\n>> Escolha uma opção [0-6]: ").strip()
        except KeyboardInterrupt:
            print("\n\nEncerrando SharlokInsta Desktop. Até logo!\n")
            sys.exit(0)

        if escolha == "1":
            fluxo_seguir_alvo()
        elif escolha == "2":
            fluxo_verificar_e_baixar()
        elif escolha == "3":
            fluxo_baixar_direto()
        elif escolha == "4":
            fluxo_historico()
        elif escolha == "5":
            fluxo_gerenciar_pool()
        elif escolha == "6":
            modo_sentinela()
        elif escolha == "0":
            print("\nEncerrando SharlokInsta Desktop. Até logo!\n")
            sys.exit(0)
        else:
            print("Opção inválida. Tente novamente.")


if __name__ == "__main__":
    main()
