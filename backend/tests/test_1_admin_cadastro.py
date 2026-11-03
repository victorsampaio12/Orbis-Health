"""
Painel do Administrador: dashboard, hub de cadastro e o CRUD completo das
3 áreas (Hospitais, Socorristas, Administradores), perfil e preferências.

Os testes rodam em sequência na mesma sessão logada (fixture `admin_page`
de escopo de classe) — cada um parte do estado deixado pelo anterior.
"""
import pytest

from apoio import login, texto_flash


class TestAdminCadastro:
    @pytest.mark.regra("HU-001")
    def test_login_admin_abre_dashboard_com_kpis(self, admin_page, servidor):
        """Login com credenciais válidas leva ao dashboard do admin."""
        login(admin_page, servidor, "admin0@t.com")

        assert "/dashboard" in admin_page.url
        assert "Login com Sucesso!" in texto_flash(admin_page)
        assert admin_page.locator(".kpi-tile").count() >= 6

    def test_api_dados_do_dashboard(self, admin_page, servidor):
        """O JSON que atualiza o dashboard sozinho traz todos os indicadores."""
        resp = admin_page.request.get(f"{servidor}/admin/dashboard-dados")
        dados = resp.json()

        assert resp.status == 200
        for chave in ("hospitais", "socorristas", "ocorrencias_ativas", "finalizadas_hoje",
                      "capacidade_hospitais", "veiculos_ativos", "ultimas_acoes"):
            assert chave in dados
        assert dados["hospitais"]["total"] == 1

    def test_hub_de_cadastro_mostra_as_tres_areas(self, admin_page, servidor):
        """A tela Cadastro mostra os 3 cartões com os contadores reais."""
        admin_page.goto(f"{servidor}/admin/")
        admin_page.wait_for_load_state("networkidle")

        assert admin_page.locator(".cadastro-card").count() == 3
        assert "1" in admin_page.inner_text(".cadastro-card-hospital")

    def test_sidebar_lista_os_tres_cadastros(self, admin_page):
        """Os 3 cadastros aparecem direto no menu lateral."""
        itens = admin_page.locator(".app-sidebar a span").all_inner_texts()

        for item in ("Dashboard", "Cadastro", "Hospitais", "Socorristas", "Administradores"):
            assert item in itens

    def test_api_sugestoes_de_endereco(self, admin_page, servidor):
        """Autocomplete de endereço devolve candidatos reais do OpenStreetMap."""
        resp = admin_page.request.get(f"{servidor}/admin/enderecos-sugestoes?texto=Hospital de Base Brasilia")
        sugestoes = resp.json()["sugestoes"]

        assert resp.status == 200
        assert len(sugestoes) >= 1
        assert sugestoes[0]["latitude"] is not None

    def test_api_geocodificar_endereco(self, admin_page, servidor):
        """Geocodificação direta (fallback de quem não usa o autocomplete)."""
        resp = admin_page.request.get(f"{servidor}/admin/geocodificar?endereco=Hospital de Base do Distrito Federal")
        dados = resp.json()

        assert resp.status == 200
        assert -16.1 < dados["latitude"] < -15.5
        assert -48.2 < dados["longitude"] < -47.5

    def test_criar_hospital_com_endereco_do_autocomplete(self, admin_page, servidor):
        """Cadastro de hospital escolhendo o endereço na lista de sugestões."""
        admin_page.goto(f"{servidor}/admin/hospitais/novo")
        admin_page.fill("#nome", "Hospital de Base do Distrito Federal")
        admin_page.fill("#endereco", "Hospital de Base do Distrito Federal Brasília")
        admin_page.wait_for_selector("#endereco-sugestoes li", timeout=10000)
        admin_page.locator("#endereco-sugestoes li").first.click()
        admin_page.check('input[name="tem_heliponto"]')
        admin_page.check('input[name="tem_garagem"]')
        admin_page.fill("#capacidade_maxima", "12")
        admin_page.fill("#responsavel_nome", "Carlos Mendes")
        admin_page.fill("#email", "hospbase@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert admin_page.url.endswith("/admin/hospitais")
        assert "Hospital criado com sucesso!" in texto_flash(admin_page)
        assert "Hospital de Base do Distrito Federal" in admin_page.inner_text(".admin-table")

    def test_hospital_criado_tem_coordenadas_no_banco(self, admin_page, db_app):
        """O endereço virou latitude/longitude de verdade no banco."""
        from app import db
        from app.models.hospital import Hospital

        db.session.expire_all()
        hospital = Hospital.query.filter_by(nome="Hospital de Base do Distrito Federal").one()

        assert hospital.latitude is not None
        assert hospital.longitude is not None
        assert hospital.tem_heliponto and hospital.tem_garagem
        assert hospital.usuario.email == "hospbase@t.com"

    def test_editar_hospital_atualiza_capacidade(self, admin_page, servidor):
        href = admin_page.locator("tr", has_text="Hospital de Base").locator(
            'a:has-text("Editar")'
        ).get_attribute("href")
        admin_page.goto(f"{servidor}{href}")
        assert admin_page.input_value("#capacidade_maxima") == "12"

        admin_page.fill("#capacidade_maxima", "20")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "Hospital atualizado com sucesso!" in texto_flash(admin_page)
        assert "20" in admin_page.locator("tr", has_text="Hospital de Base").inner_text()

    @pytest.mark.regra("RN-015")
    def test_desativar_hospital(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/hospitais")
        admin_page.locator("tr", has_text="Hospital Santa Luzia").locator(
            'button:has-text("Desativar")'
        ).click()
        admin_page.wait_for_load_state("networkidle")

        assert "Hospital desativado com sucesso!" in texto_flash(admin_page)
        assert "Desativado" in admin_page.locator("tr", has_text="Hospital Santa Luzia").inner_text()

    def test_criar_socorrista(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/socorristas/novo")
        admin_page.fill("#nome", "Ana Souza")
        admin_page.fill("#matricula", "SOC-001")
        admin_page.fill("#email", "soc@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "Socorrista criado com sucesso!" in texto_flash(admin_page)
        assert "Ana Souza" in admin_page.inner_text(".admin-table")

    def test_editar_socorrista_persiste_telefone(self, admin_page, servidor):
        href = admin_page.locator("tr", has_text="Ana Souza").locator(
            'a:has-text("Editar")'
        ).get_attribute("href")
        admin_page.goto(f"{servidor}{href}")
        admin_page.fill("#telefone", "(61) 99876-5432")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")
        assert "Socorrista atualizado com sucesso!" in texto_flash(admin_page)

        admin_page.goto(f"{servidor}{href}")
        assert admin_page.input_value("#telefone") == "(61) 99876-5432"

    @pytest.mark.regra("RN-014")
    def test_criar_e_desativar_socorrista(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/socorristas/novo")
        admin_page.fill("#nome", "Socorrista Descartável")
        admin_page.fill("#matricula", "SOC-999")
        admin_page.fill("#email", "socdescartavel@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        admin_page.locator("tr", has_text="Socorrista Descartável").locator(
            'button:has-text("Desativar")'
        ).click()
        admin_page.wait_for_load_state("networkidle")

        assert "Socorrista desativado com sucesso!" in texto_flash(admin_page)
        assert "Inativo" in admin_page.locator("tr", has_text="Socorrista Descartável").inner_text()

    def test_criar_editar_e_desativar_admin(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/admin/admins/novo")
        admin_page.fill("#nome", "Admin Demonstração")
        admin_page.fill("#email", "admindemo@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")
        assert "Admin criado com sucesso!" in texto_flash(admin_page)

        href = admin_page.locator("tr", has_text="Admin Demonstração").locator(
            'a:has-text("Editar")'
        ).get_attribute("href")
        admin_page.goto(f"{servidor}{href}")
        admin_page.fill("#nome", "Admin Demonstração Silva")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")
        assert "Admin Demonstração Silva" in admin_page.inner_text(".admin-table")

        admin_page.locator("tr", has_text="Admin Demonstração Silva").locator(
            'button:has-text("Desativar")'
        ).click()
        admin_page.wait_for_load_state("networkidle")
        assert "Desativado" in admin_page.locator("tr", has_text="Admin Demonstração Silva").inner_text()

    def test_excluir_admin(self, admin_page, servidor):
        """Exclusão com confirmação (diálogo aceito automaticamente)."""
        admin_page.goto(f"{servidor}/admin/admins/novo")
        admin_page.fill("#nome", "Admin Para Excluir")
        admin_page.fill("#email", "adminexcluir@t.com")
        admin_page.fill("#senha", "Senha@123")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        admin_page.locator("tr", has_text="Admin Para Excluir").locator(
            'button:has-text("Excluir")'
        ).click()
        admin_page.wait_for_load_state("networkidle")

        assert "Admin excluído com sucesso!" in texto_flash(admin_page)
        assert "Admin Para Excluir" not in admin_page.inner_text(".admin-table")

    def test_dashboard_reflete_os_cadastros_e_a_auditoria(self, admin_page, servidor):
        """Depois dos cadastros, os KPIs e o log de auditoria batem."""
        resp = admin_page.request.get(f"{servidor}/admin/dashboard-dados")
        dados = resp.json()

        assert dados["hospitais"] == {"total": 2, "ativos": 1}
        assert dados["socorristas"] == {"total": 2, "ativos": 1}
        assert len(dados["ultimas_acoes"]) > 0

        admin_page.goto(f"{servidor}/dashboard")
        admin_page.wait_for_load_state("networkidle")
        auditoria = admin_page.inner_text(".dash-auditoria-lista")
        assert "Admin Zero" in auditoria
        # mostra o nome de quem foi afetado, não só o id
        assert "desativou administrador Admin Demonstração Silva" in auditoria
        assert "desativou socorrista Socorrista Descartável" in auditoria

    def test_atualizar_perfil(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/perfil")
        admin_page.fill("#nome", "Admin Zero Silva")
        admin_page.locator('form[action$="/perfil"] button[type="submit"]').click()
        admin_page.wait_for_load_state("networkidle")

        assert "Perfil atualizado com sucesso!" in texto_flash(admin_page)
        assert admin_page.input_value("#nome") == "Admin Zero Silva"

    def test_salvar_preferencias(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/preferencias")
        admin_page.check('input[name="formato_hora"][value="12h"]')
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        assert "Preferências salvas com sucesso!" in texto_flash(admin_page)
        assert admin_page.is_checked('input[name="formato_hora"][value="12h"]')

    def test_recolher_menu_lateral_salva_preferencia(self, admin_page):
        """O botão de recolher o menu salva a preferência via API."""
        with admin_page.expect_response("**/preferencias/menu") as resposta:
            admin_page.click("#sidebar-toggle")

        assert resposta.value.status == 200
        assert resposta.value.json() == {"ok": True}

        with admin_page.expect_response("**/preferencias/menu"):
            admin_page.click("#sidebar-toggle")

    def test_service_worker_e_servido(self, admin_page, servidor):
        """O /sw.js (service worker do app) é servido como JavaScript."""
        resp = admin_page.request.get(f"{servidor}/sw.js")

        assert resp.status == 200
        assert "javascript" in resp.headers["content-type"]

    def test_logout_admin(self, admin_page, servidor):
        admin_page.goto(f"{servidor}/logout")

        assert "/login" in admin_page.url
        assert "Usuário deslogado com sucesso!" in texto_flash(admin_page)
