"""
Testes NEGATIVOS: o que o sistema deve recusar.

- Autenticação: senha errada, e-mail inexistente, bloqueio por tentativas,
  hospital desativado (RN-015), rotas protegidas sem login.
- Autorização: cada perfil tentando acessar o que não é dele (admin x
  socorrista x hospital) e ocorrências de terceiros (RN-007/RN-008/RN-016).
- Validação no SERVIDOR (com a validação do navegador desligada):
  e-mail duplicado/ inválido, senha curta, campos obrigatórios,
  capacidade inválida, troca de senha.
- Regras de negócio: último admin ativo (RN-020), socorrista inativo
  (RN-014), hospital lotado (RN-006) e incompatível (RN-003) revalidados
  no servidor mesmo burlando a tela, chat encerrado (RN-022).

Roda depois de test_1 e test_2 e aproveita os dados criados por eles.
"""
import re

import pytest

from apoio import desligar_validacao_html, emitir_socket, login, logout, texto_flash


@pytest.fixture(scope="class")
def cenarios(db_app):
    """Prepara (arrange) dados que não fazem sentido criar pela interface
    no meio de um teste negativo: um hospital já lotado, um hospital sem
    garagem e uma conta só pra ser bloqueada."""
    from app import db
    from app.models.ocorrencia import (
        Ocorrencia, StatusOcorrenciaEnum, TipoRotaEnum, VeiculoEnum,
    )
    from app.models.usuario import Usuario
    from app.services import cadastro_service

    admin0 = Usuario.query.filter_by(email="admin0@t.com").one()

    lotado = cadastro_service.criar_hospital(
        {
            "nome": "Hospital Lotado Teste", "endereco": "SMHN, Brasília - DF",
            "latitude": "-15.7801", "longitude": "-47.8895",
            "capacidade_maxima": "1", "tem_garagem": "on", "tem_heliponto": "",
            "responsavel_nome": "Resp Lotado", "email": "hosplotado@t.com", "senha": "Senha@123",
        },
        admin0,
    )
    so_heliponto = cadastro_service.criar_hospital(
        {
            "nome": "Hospital Só Heliponto", "endereco": "Lago Sul, Brasília - DF",
            "latitude": "-15.8350", "longitude": "-47.8700",
            "capacidade_maxima": "10", "tem_garagem": "", "tem_heliponto": "on",
            "responsavel_nome": "Resp Heli", "email": "hospheli@t.com", "senha": "Senha@123",
        },
        admin0,
    )
    ocupante = cadastro_service.criar_socorrista(
        {"nome": "Socorrista Ocupante", "matricula": "SOC-500",
         "email": "ocupante@t.com", "senha": "Senha@123"},
        admin0,
    )
    cadastro_service.criar_socorrista(
        {"nome": "Socorrista Bloqueio", "matricula": "SOC-501",
         "email": "bloqueio@t.com", "senha": "Senha@123"},
        admin0,
    )
    db.session.add(Ocorrencia(
        socorrista_id=ocupante.id, hospital_id=lotado.id, veiculo=VeiculoEnum.ambulancia,
        status=StatusOcorrenciaEnum.em_transporte, tipo_rota=TipoRotaEnum.terrestre,
        local="Ocorrência que ocupa o único leito",
    ))
    db.session.commit()
    return {"lotado_id": lotado.id, "so_heliponto_id": so_heliponto.id, "dados": {}}


def _url_de_uma_foto(servidor):
    """Uma foto anexada no test_2 (prontuário da ocorrência da Ana)."""
    from app import db
    from app.models.anexo import AnexoPaciente

    db.session.expire_all()
    anexo = AnexoPaciente.query.first()
    return f"{servidor}/ocorrencias/{anexo.paciente.ocorrencia_id}/anexos/{anexo.id}"


@pytest.mark.usefixtures("cenarios")
class TestSegurancaEValidacao:
    # ------------------------------------------------------------ sem login

    def test_raiz_sem_login_vai_para_o_login(self, anon_page, servidor):
        anon_page.goto(f"{servidor}/")

        assert anon_page.url.startswith(f"{servidor}/login")

    @pytest.mark.parametrize("rota", [
        "/dashboard", "/admin/", "/admin/hospitais", "/admin/dashboard-dados",
        "/ocorrencias/novo", "/ocorrencias/1", "/inbox/", "/perfil",
        "/preferencias", "/emergencias/historico",
    ])
    def test_rota_protegida_exige_login(self, anon_page, servidor, rota):
        anon_page.goto(f"{servidor}{rota}")

        assert "/login" in anon_page.url

    def test_foto_do_prontuario_exige_login(self, anon_page, servidor, db_app):
        resp = anon_page.request.get(_url_de_uma_foto(servidor), max_redirects=0)

        assert resp.status == 302
        assert "/login" in resp.headers["location"]

    @pytest.mark.regra("HU-001")
    def test_login_com_senha_errada(self, anon_page, servidor):
        login(anon_page, servidor, "admin0@t.com", senha="SenhaErrada1")

        assert "/login" in anon_page.url
        assert "E-mail ou senha incorretos!" in texto_flash(anon_page)

    @pytest.mark.regra("HU-001")
    def test_login_com_email_inexistente_da_a_mesma_mensagem(self, anon_page, servidor):
        """Mesma mensagem da senha errada: não revela quais e-mails existem."""
        login(anon_page, servidor, "ninguem@t.com")

        assert "E-mail ou senha incorretos!" in texto_flash(anon_page)

    @pytest.mark.regra("HU-001")
    def test_bloqueio_apos_5_tentativas_erradas(self, anon_page, servidor):
        for _ in range(5):
            login(anon_page, servidor, "bloqueio@t.com", senha="Errada123")
        login(anon_page, servidor, "bloqueio@t.com")  # agora com a senha CERTA

        assert "/login" in anon_page.url
        assert "Perfil temporariamente bloqueado" in texto_flash(anon_page)

    @pytest.mark.regra("RN-015")
    def test_usuario_de_hospital_desativado_nao_loga(self, anon_page, servidor):
        login(anon_page, servidor, "hospapoio@t.com")

        assert "/login" in anon_page.url
        assert "Perfil temporariamente bloqueado" in texto_flash(anon_page)

    # ------------------------------------------------------------- admin

    def test_cadastro_com_email_duplicado(self, admin_page, servidor):
        login(admin_page, servidor, "admin0@t.com")
        admin_page.goto(f"{servidor}/admin/socorristas/novo")
        admin_page.fill("#nome", "Duplicado")
        admin_page.fill("#matricula", "SOC-777")
        admin_page.fill("#email", "soc@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "E-mail já cadastrado." in texto_flash(admin_page)
        assert admin_page.input_value("#nome") == "Duplicado"  # mantém o que foi digitado

    def test_cadastro_com_matricula_duplicada(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/socorristas/novo")
        admin_page.fill("#nome", "Outro")
        admin_page.fill("#matricula", "SOC-001")
        admin_page.fill("#email", "outro@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "Matrícula já cadastrada." in texto_flash(admin_page)

    def test_cadastro_com_senha_curta(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/admins/novo")
        admin_page.fill("#nome", "Senha Curta")
        admin_page.fill("#email", "curta@t.com")
        admin_page.fill("#senha", "123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "A senha deve ter pelo menos 6 caracteres." in texto_flash(admin_page)

    def test_cadastro_com_email_invalido_validado_no_servidor(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/admins/novo")
        desligar_validacao_html(admin_page)
        admin_page.fill("#nome", "Email Ruim")
        admin_page.fill("#email", "nao-e-um-email")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "E-mail inválido." in texto_flash(admin_page)

    def test_campo_obrigatorio_validado_no_servidor(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/hospitais/novo")
        desligar_validacao_html(admin_page)
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "O campo nome do hospital é obrigatório." in texto_flash(admin_page)

    def test_capacidade_invalida(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/hospitais")
        href = admin_page.locator("tr", has_text="Hospital de Base").locator(
            'a:has-text("Editar")'
        ).get_attribute("href")
        admin_page.goto(f"{servidor}{href}")
        desligar_validacao_html(admin_page)
        admin_page.fill("#capacidade_maxima", "-5")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "Capacidade máxima deve ser um número inteiro positivo." in texto_flash(admin_page)

    @pytest.mark.regra("RN-020")
    def test_nao_desativa_o_ultimo_admin_ativo(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/admins")
        admin_page.locator("tr", has_text="admin0@t.com").locator('button:has-text("Desativar")').click()
        admin_page.wait_for_load_state("networkidle")

        assert "Não é possível desativar: este é o último admin ativo do sistema." in texto_flash(admin_page)
        assert "Ativo" in admin_page.locator("tr", has_text="admin0@t.com").inner_text()

    @pytest.mark.regra("RN-020")
    def test_nao_exclui_o_ultimo_admin_ativo(self, admin_page, servidor):
        admin_page.locator("tr", has_text="admin0@t.com").locator('button:has-text("Excluir")').click()
        admin_page.wait_for_load_state("networkidle")

        assert "Não é possível excluir: este é o último admin ativo do sistema." in texto_flash(admin_page)
        assert admin_page.locator("tr", has_text="admin0@t.com").count() == 1

    def test_troca_de_senha_com_senha_atual_errada(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/perfil")
        admin_page.fill("#senha_atual", "NaoEhEssa1")
        admin_page.fill("#nova_senha", "NovaSenha1")
        admin_page.fill("#confirmacao", "NovaSenha1")
        admin_page.locator('form[action$="/perfil/senha"] button[type="submit"]').click()
        admin_page.wait_for_load_state("networkidle")

        assert "Senha atual incorreta." in texto_flash(admin_page)

    def test_troca_de_senha_com_confirmacao_diferente(self, admin_page, servidor):
        admin_page.fill("#senha_atual", "Senha@123")
        admin_page.fill("#nova_senha", "NovaSenha1")
        admin_page.fill("#confirmacao", "OutraSenha1")
        admin_page.locator('form[action$="/perfil/senha"] button[type="submit"]').click()
        admin_page.wait_for_load_state("networkidle")

        assert "A confirmação da senha não confere." in texto_flash(admin_page)

    def test_admin_nao_acessa_telas_de_socorrista(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/ocorrencias/novo")

        assert "/dashboard" in admin_page.url
        assert "restrita a socorristas" in texto_flash(admin_page)

    @pytest.mark.regra("RN-007")
    def test_admin_nao_ve_ocorrencia(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/ocorrencias/1")

        assert "Acesso não autorizado" in texto_flash(admin_page)

    @pytest.mark.regra("RN-016")
    def test_admin_nao_le_o_chat_da_ocorrencia(self, admin_page, servidor):
        resp = admin_page.request.get(f"{servidor}/ocorrencias/1/mensagens")

        assert resp.status == 403
        assert resp.json()["erro"] == "Acesso não autorizado"

    @pytest.mark.regra("RN-007")
    def test_admin_nao_ve_fotos_do_prontuario(self, admin_page, servidor, db_app):
        resp = admin_page.request.get(_url_de_uma_foto(servidor))

        assert resp.status == 403

    @pytest.mark.regra("RN-016")
    @pytest.mark.eventos_ws("enviar_mensagem", "erro_mensagem")
    def test_admin_nao_envia_mensagem_pelo_websocket(self, admin_page):
        erro = emitir_socket(
            admin_page, "enviar_mensagem", {"ocorrencia_id": 1, "conteudo": "intruso"},
            aguardar="erro_mensagem",
        )

        assert erro is not None
        assert erro["erro"] == "Acesso não autorizado"

    # ----------------------------------------------- socorrista inativo

    @pytest.mark.regra("RN-014")
    def test_socorrista_inativo_loga_mas_nao_cria_ocorrencia(self, soc_page, servidor):
        login(soc_page, servidor, "socdescartavel@t.com")
        assert "/ocorrencias/novo" in soc_page.url

        soc_page.wait_for_function("document.getElementById('local').value.length > 0", timeout=10000)
        soc_page.select_option("#veiculo", "ambulancia")
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "Socorrista inativo não pode operar" in texto_flash(soc_page)
        assert "/ocorrencias/novo" in soc_page.url

    def test_socorrista_nao_acessa_admin(self, soc_page, servidor):
        soc_page.goto(f"{servidor}/admin/hospitais")

        assert "restrita a administradores" in texto_flash(soc_page)

    def test_socorrista_nao_acessa_api_do_dashboard(self, soc_page, servidor):
        resp = soc_page.request.get(f"{servidor}/admin/dashboard-dados", max_redirects=0)

        assert resp.status == 302

    @pytest.mark.regra("RN-007", "RN-008")
    def test_socorrista_nao_ve_ocorrencia_de_outro(self, soc_page, servidor):
        soc_page.goto(f"{servidor}/ocorrencias/1")
        assert "Acesso não autorizado" in texto_flash(soc_page)

        soc_page.goto(f"{servidor}/ocorrencias/1/pacientes")
        assert "Acesso não autorizado" in texto_flash(soc_page)

    @pytest.mark.regra("RN-007")
    def test_socorrista_nao_ve_fotos_de_outra_ocorrencia(self, soc_page, servidor, db_app):
        resp = soc_page.request.get(_url_de_uma_foto(servidor))

        assert resp.status == 403

    @pytest.mark.regra("RN-008")
    def test_socorrista_nao_altera_localizacao_de_outro(self, soc_page, servidor):
        resp = soc_page.request.post(f"{servidor}/ocorrencias/1/localizacao", data={"lat": 0, "lng": 0})

        assert resp.status == 403

    def test_socorrista_nao_acessa_historico_do_hospital(self, soc_page, servidor):
        resp = soc_page.request.get(f"{servidor}/emergencias/historico")

        assert resp.status == 403

    # --------------------------------------- regras na seleção de hospital

    @pytest.mark.regra("RN-006")
    def test_hospital_lotado_aparece_bloqueado(self, soc_page, servidor, cenarios):
        logout(soc_page, servidor)
        login(soc_page, servidor, "soc@t.com")
        soc_page.wait_for_function("document.getElementById('local').value.length > 0", timeout=10000)
        soc_page.select_option("#veiculo", "ambulancia")
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")
        cenarios["dados"]["id"] = int(re.search(r"/ocorrencias/(\d+)$", soc_page.url).group(1))

        soc_page.goto(f"{servidor}/ocorrencias/{cenarios['dados']['id']}/hospitais")
        card = soc_page.locator(".hospital-card", has_text="Hospital Lotado Teste")

        assert "Lotado" in card.inner_text()
        assert card.locator("button").is_disabled()

    @pytest.mark.regra("RN-006")
    def test_hospital_lotado_e_recusado_mesmo_burlando_a_tela(self, soc_page):
        """Reabilita o botão desabilitado e envia: o servidor revalida."""
        card = soc_page.locator(".hospital-card", has_text="Hospital Lotado Teste")
        card.locator("button").evaluate("b => b.disabled = false")
        card.locator("button").click()
        soc_page.wait_for_load_state("networkidle")

        assert "Hospital selecionado lotado!" in texto_flash(soc_page)

    @pytest.mark.regra("RN-003")
    def test_hospital_incompativel_nao_aparece_e_e_recusado(self, soc_page, servidor, cenarios):
        """Ambulância precisa de garagem: o hospital só com heliponto não é
        listado, e forçar o id dele no formulário também é recusado."""
        soc_page.goto(f"{servidor}/ocorrencias/{cenarios['dados']['id']}/hospitais")
        assert "Hospital Só Heliponto" not in soc_page.inner_text(".split-pane-list")

        card = soc_page.locator(".hospital-card", has_text="Hospital de Base")
        card.locator('input[name="hospital_id"]').evaluate(
            "(el, id) => el.value = id", cenarios["so_heliponto_id"]
        )
        card.locator("button").click()
        soc_page.wait_for_load_state("networkidle")

        assert "Hospital Inválido — Tipo de Veículo Incompatível" in texto_flash(soc_page)

    @pytest.mark.regra("RN-022")
    @pytest.mark.eventos_ws("enviar_mensagem", "erro_mensagem")
    def test_chat_encerrado_recusa_mensagem(self, soc_page, servidor):
        """A ocorrência 1 (test_2) já foi finalizada: o servidor recusa
        mensagem nova mesmo enviada direto pelo WebSocket."""
        soc_page.goto(f"{servidor}/ocorrencias/1")
        erro = emitir_socket(
            soc_page, "enviar_mensagem", {"ocorrencia_id": 1, "conteudo": "depois do fim"},
            aguardar="erro_mensagem",
        )

        assert erro is not None
        assert erro["erro"] == "Esta conversa foi encerrada."

    # ------------------------------------------------------------ hospital

    def test_hospital_nao_acessa_admin_nem_telas_de_socorrista(self, hosp_page, servidor):
        login(hosp_page, servidor, "hospbase@t.com")

        hosp_page.goto(f"{servidor}/admin/socorristas")
        assert "restrita a administradores" in texto_flash(hosp_page)

        hosp_page.goto(f"{servidor}/ocorrencias/novo")
        assert "restrita a socorristas" in texto_flash(hosp_page)

    @pytest.mark.regra("RN-007")
    def test_hospital_nao_ve_ocorrencia_destinada_a_outro(self, hosp_page, servidor, cenarios):
        """A ocorrência nova da Ana ainda não tem destino: este hospital não
        tem acesso a ela."""
        hosp_page.goto(f"{servidor}/ocorrencias/{cenarios['dados']['id']}")

        assert "Acesso não autorizado" in texto_flash(hosp_page)

    def test_troca_de_senha_com_sucesso(self, hosp_page, servidor):
        """Caminho feliz da troca de senha: a antiga para de funcionar."""
        hosp_page.goto(f"{servidor}/perfil")
        hosp_page.fill("#senha_atual", "Senha@123")
        hosp_page.fill("#nova_senha", "NovaSenha@456")
        hosp_page.fill("#confirmacao", "NovaSenha@456")
        hosp_page.locator('form[action$="/perfil/senha"] button[type="submit"]').click()
        hosp_page.wait_for_load_state("networkidle")
        assert "Senha alterada com sucesso!" in texto_flash(hosp_page)

        logout(hosp_page, servidor)
        login(hosp_page, servidor, "hospbase@t.com", senha="Senha@123")
        assert "E-mail ou senha incorretos!" in texto_flash(hosp_page)

        login(hosp_page, servidor, "hospbase@t.com", senha="NovaSenha@456")
        assert "/dashboard" in hosp_page.url
