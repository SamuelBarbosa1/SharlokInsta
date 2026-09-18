# scraper/__init__.py
from .browser import criar_contexto_desktop
from .profile import obter_info_perfil
from .actions import enviar_follow_com_conta, cancelar_solicitacao_pendente
from .extractor import extrair_e_baixar_fotos
