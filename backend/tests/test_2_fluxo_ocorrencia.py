"""
Jornada completa de uma emergência, com socorrista e hospital em duas
sessões de navegador SIMULTÂNEAS (`soc_page` e `hosp_page`): criação da
ocorrência, seleção de hospital, rota via OSRM, notificações e chat em
tempo real (Socket.IO), prontuário, trajeto, chegada, finalização,
relatório, inbox e histórico.

Depende de test_1 já ter criado o "Hospital de Base do Distrito Federal" e
a socorrista "Ana Souza" (o pytest roda os arquivos em ordem alfabética).
"""
import re

import pytest

from apoio import desligar_validacao_html, esperar_aviso, login, texto_flash


@pytest.fixture(scope="class")
def contexto():
    """Guarda o id da ocorrência compartilhada pelos testes da classe."""
    return {}


def _ocorrencia(contexto):
    from app import db
    from app.models.ocorrencia import Ocorrencia

    db.session.expire_all()
    return db.session.get(Ocorrencia, contexto["id"])


class TestFluxoOcorrencia:
    @pytest.mark.regra("HU-013")
    def test_socorrista_sem_ocorrencia_cai_no_formulario_com_local(self, soc_page, servidor):
        """Sem ocorrência ativa, o dashboard do socorrista abre o formulário,
        já com o local preenchido pela geolocalização do navegador."""
        login(soc_page, servidor, "soc@t.com")
        soc_page.wait_for_function("document.getElementById('local').value.length > 0", timeout=10000)

        assert "/ocorrencias/novo" in soc_page.url
        assert "Brasília" in soc_page.input_value("#local")

    def test_api_geocodificacao_reversa(self, soc_page, servidor):
        resp = soc_page.request.get(f"{servidor}/ocorrencias/geocodificar-reverso?lat=-15.801&lng=-47.887")

        assert resp.status == 200
        assert "Brasília" in resp.json()["endereco"]

    def test_criar_ocorrencia(self, soc_page, contexto, db_app):
        soc_page.select_option("#veiculo", "ambulancia")
        soc_page.fill("#comentarios", "Vítima consciente, relatando dor no peito.")
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        m = re.search(r"/ocorrencias/(\d+)$", soc_page.url)
        assert m is not None
        contexto["id"] = int(m.group(1))
        assert "Ocorrência Salva com Sucesso!" in texto_flash(soc_page)

        ocorrencia = _ocorrencia(contexto)
        assert ocorrencia.status.value == "aberta"
        assert ocorrencia.latitude_atual is not None

    def test_hospital_comeca_sem_emergencias(self, hosp_page, servidor):
        login(hosp_page, servidor, "hospbase@t.com")

        assert "/dashboard" in hosp_page.url
        assert hosp_page.locator(".emg-card").count() == 0

    @pytest.mark.regra("RN-003", "RN-015")
    def test_lista_so_hospitais_ativos_e_compativeis(self, soc_page, servidor, contexto):
        """O Hospital Santa Luzia, desativado no test_1, não é oferecido."""
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/hospitais")
        texto = soc_page.inner_text(".split-pane-list")

        assert "Hospital de Base do Distrito Federal" in texto
        assert "Hospital Santa Luzia" not in texto
        assert "0 de 20 leitos de emergência ocupados · 20 leitos livres" in texto

    @pytest.mark.regra("RN-004", "RN-005")
    def test_selecionar_hospital(self, soc_page, contexto, db_app):
        soc_page.locator(".hospital-card", has_text="Hospital de Base").locator(
            'button:has-text("Selecionar")'
        ).click()
        soc_page.wait_for_load_state("networkidle")

        assert "Hospital de destino confirmado!" in texto_flash(soc_page)
        assert "Em transporte" in soc_page.locator(".status-badge").first.inner_text()
        ocorrencia = _ocorrencia(contexto)
        assert ocorrencia.status.value == "em_transporte"
        assert ocorrencia.tipo_rota.value == "terrestre"

    @pytest.mark.eventos_ws("entrar_sala_hospital", "nova_emergencia")
    def test_hospital_recebe_nova_emergencia_em_tempo_real(self, hosp_page, contexto):
        """Sem recarregar a página, o card da emergência aparece pro hospital."""
        codigo = f"EMG-{contexto['id']:04d}"
        hosp_page.locator(".emg-card", has_text=codigo).wait_for(timeout=15000)

        assert hosp_page.locator(".emg-card", has_text=codigo).count() == 1
        assert "Ana Souza" in hosp_page.locator(".emg-card", has_text=codigo).inner_text()

    def test_gerenciar_pacientes_e_botao_principal(self, soc_page):
        """O botão "Gerenciar pacientes" segue o padrão vermelho dos botões
        principais do sistema."""
        botao = soc_page.locator('a:has-text("Gerenciar pacientes")')

        assert "btn-primary" in botao.get_attribute("class")
        assert botao.evaluate("b => getComputedStyle(b).backgroundColor") == "rgb(140, 43, 43)"
        assert botao.evaluate("b => getComputedStyle(b).color") == "rgb(255, 255, 255)"

    @pytest.mark.eventos_ws("emergencia_cancelada")
    def test_voltar_desfaz_a_escolha_e_avisa_o_hospital(self, soc_page, hosp_page, servidor, contexto, db_app):
        """Antes de iniciar o trajeto, "Voltar" devolve a ocorrência para a
        lista de hospitais, e o hospital abandonado é avisado em tempo real."""
        soc_page.click("#form-voltar-hospitais button")
        soc_page.wait_for_load_state("networkidle")

        assert soc_page.url.endswith(f"/ocorrencias/{contexto['id']}/hospitais")
        assert "Seleção desfeita" in texto_flash(soc_page)
        ocorrencia = _ocorrencia(contexto)
        assert ocorrencia.status.value == "aberta"
        assert ocorrencia.hospital_id is None

        esperar_aviso(hosp_page, "não vem mais para este hospital")
        hosp_page.wait_for_function("document.querySelectorAll('.emg-card').length === 0", timeout=8000)
        assert hosp_page.locator(".emg-card").count() == 0

    def test_escolher_o_hospital_de_novo(self, soc_page, hosp_page, contexto, db_app):
        soc_page.locator(".hospital-card", has_text="Hospital de Base").locator(
            'button:has-text("Selecionar")'
        ).click()
        soc_page.wait_for_load_state("networkidle")

        assert _ocorrencia(contexto).status.value == "em_transporte"
        hosp_page.locator(".emg-card", has_text=f"EMG-{contexto['id']:04d}").wait_for(timeout=15000)

    def test_gerar_rota(self, soc_page, contexto, db_app):
        soc_page.click("#btn-gerar-rota")
        soc_page.wait_for_load_state("networkidle")

        assert "Rota gerada com sucesso!" in texto_flash(soc_page)
        assert "km" in soc_page.inner_text("#distancia-estimada")
        assert "min" in soc_page.inner_text("#tempo-estimado")
        assert _ocorrencia(contexto).rota_geometria is not None

    @pytest.mark.eventos_ws("atualizar_localizacao", "localizacao_atualizada")
    def test_atualizar_localizacao_por_websocket(self, soc_page, contexto, db_app):
        """Posição enviada pelo socket é gravada e retransmitida pra sala."""
        payload = soc_page.evaluate(
            """(id) => new Promise((resolve) => {
                window.OrbisSocket.once("localizacao_atualizada", resolve);
                window.OrbisSocket.emit("atualizar_localizacao", {ocorrencia_id: id, lat: -15.8045, lng: -47.8884});
                setTimeout(() => resolve(null), 5000);
            })""",
            contexto["id"],
        )

        assert payload is not None
        assert payload["lat"] == pytest.approx(-15.8045)
        assert payload["distancia_estimada_km"] > 0.2
        assert _ocorrencia(contexto).latitude_atual == pytest.approx(-15.8045)

    def test_api_salvar_localizacao_por_http(self, soc_page, servidor, contexto, db_app):
        """Fallback HTTP usado quando a permissão de localização chega depois."""
        resp = soc_page.request.post(
            f"{servidor}/ocorrencias/{contexto['id']}/localizacao",
            data={"lat": -15.8040, "lng": -47.8884},
        )

        assert resp.status == 200
        assert resp.json() == {"ok": True}
        assert _ocorrencia(contexto).latitude_atual == pytest.approx(-15.8040)

    @pytest.mark.regra("RN-007")
    @pytest.mark.eventos_ws("entrar_sala_ocorrencia")
    def test_hospital_abre_a_ocorrencia(self, hosp_page, contexto):
        codigo = f"EMG-{contexto['id']:04d}"
        hosp_page.locator(".emg-card", has_text=codigo).locator('a:has-text("Abrir ocorrência")').click()
        hosp_page.wait_for_load_state("networkidle")

        assert hosp_page.url.endswith(f"/ocorrencias/{contexto['id']}")
        assert hosp_page.locator("#chat-form").count() == 1

    @pytest.mark.regra("HU-018")
    @pytest.mark.eventos_ws("enviar_mensagem", "mensagem_recebida")
    def test_chat_em_tempo_real(self, soc_page, hosp_page):
        soc_page.fill("#chat-input", "A caminho com paciente consciente, sinais vitais estáveis.")
        soc_page.click('#chat-form button[type="submit"]')
        hosp_page.wait_for_function(
            "document.getElementById('chat-mensagens').innerText.includes('A caminho com paciente')",
            timeout=5000,
        )

        hosp_page.fill("#chat-input", "Leito de emergência já reservado.")
        hosp_page.click('#chat-form button[type="submit"]')
        soc_page.wait_for_function(
            "document.getElementById('chat-mensagens').innerText.includes('Leito de emergência')",
            timeout=5000,
        )

        assert "Leito de emergência já reservado." in soc_page.inner_text("#chat-mensagens")
        assert "A caminho com paciente" in hosp_page.inner_text("#chat-mensagens")

    @pytest.mark.regra("HU-019")
    def test_api_historico_de_mensagens(self, soc_page, servidor, contexto):
        resp = soc_page.request.get(f"{servidor}/ocorrencias/{contexto['id']}/mensagens")
        dados = resp.json()

        assert resp.status == 200
        assert dados["chat_encerrado"] is False
        assert [m["remetente_nome"] for m in dados["mensagens"]] == ["Ana Souza", "Carlos Mendes"]

    def test_cadastrar_paciente(self, soc_page, servidor, contexto):
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/pacientes")
        assert "Nenhum paciente cadastrado ainda." in soc_page.inner_text(".paciente-cards")

        soc_page.click('a:has-text("Adicionar paciente")')
        soc_page.fill("#nome", "Maria Teste")
        soc_page.fill("#idade", "54")
        soc_page.check('input[name="documentos_em_maos"][value="sim"]')
        soc_page.fill("#motivo_chamado", "Dor torácica intensa com início súbito há 20 minutos.")
        soc_page.fill("#pressao_arterial", "140/90")
        soc_page.fill("#frequencia_cardiaca", "98")
        soc_page.check('input[name="estavel"]')
        soc_page.fill("#diagnostico", "Suspeita de síndrome coronariana aguda.")
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "Prontuário Salvo com Sucesso!" in texto_flash(soc_page)
        assert "Maria Teste" in soc_page.inner_text(".paciente-cards")

    def test_paciente_sem_nome_e_rejeitado_pelo_servidor(self, soc_page, servidor, contexto):
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/pacientes/novo")
        desligar_validacao_html(soc_page)
        soc_page.fill("#motivo_chamado", "Teste sem nome")
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "O campo nome é obrigatório." in texto_flash(soc_page)

    def test_editar_paciente_nao_mostra_literal_none(self, soc_page, servidor, contexto):
        """REGRESSÃO de bug real: campos opcionais nunca preenchidos (CPF,
        frequência respiratória, observação...) apareciam com o texto
        "None" ao reabrir o prontuário e, se reenviados, viravam dado
        gravado. Corrigido em ocorrencia_controller.editar_paciente."""
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/pacientes")
        soc_page.click('a:has-text("Prontuário Médico")')
        soc_page.wait_for_load_state("networkidle")

        assert soc_page.input_value("#cpf") == ""
        assert soc_page.input_value("#frequencia_respiratoria") == ""
        assert soc_page.input_value("#observacao") == ""

        soc_page.check('input[name="melhorando"]')
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")
        assert "Prontuário Atualizado com Sucesso!" in texto_flash(soc_page)

    def test_anexar_fotos_no_prontuario(self, soc_page, servidor, contexto, tmp_path):
        """Fotos escolhidas aparecem em prévia antes de enviar e ficam salvas
        no prontuário depois."""
        from PIL import Image

        png = tmp_path / "ferimento.png"
        Image.new("RGB", (800, 600), (200, 60, 60)).save(png)
        jpg = tmp_path / "ecg_do_celular.jpg"
        exif = Image.Exif()
        exif[0x010F] = "CelularDoSocorrista"  # metadado que deve ser descartado
        Image.new("RGB", (3000, 2000), (240, 240, 240)).save(jpg, exif=exif)

        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/pacientes")
        soc_page.click('a:has-text("Prontuário Médico")')
        soc_page.wait_for_load_state("networkidle")
        soc_page.set_input_files("#anexos", [str(png), str(jpg)])
        assert soc_page.locator("#anexos-previa .anexo-novo img").count() == 2

        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")
        assert "Prontuário Atualizado com Sucesso!" in texto_flash(soc_page)

        soc_page.click('a:has-text("Prontuário Médico")')
        soc_page.wait_for_load_state("networkidle")
        assert soc_page.locator(".anexo-existente").count() == 2

    def test_arquivo_que_nao_e_imagem_e_recusado(self, soc_page, tmp_path):
        """Um arquivo qualquer renomeado para .jpg é recusado pelo servidor, e
        nada do formulário é salvo."""
        falso = tmp_path / "nao_sou_foto.jpg"
        falso.write_text("isto é texto, não uma imagem")

        soc_page.fill("#observacao", "esta alteração não deve ser salva")
        soc_page.set_input_files("#anexos", str(falso))
        soc_page.locator("#anexos-previa .anexo-invalido").wait_for(timeout=5000)
        assert "Não é uma imagem válida" in soc_page.inner_text("#anexos-previa")
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert 'não é uma imagem válida' in texto_flash(soc_page)
        soc_page.goto(soc_page.url)
        assert soc_page.locator(".anexo-existente").count() == 2
        assert "esta alteração não deve ser salva" not in soc_page.input_value("#observacao")

    @pytest.mark.regra("RN-007")
    def test_hospital_ve_as_fotos_do_prontuario(self, hosp_page, servidor, contexto):
        """O hospital de destino vê a galeria, abre a foto em tela cheia, e a
        imagem servida foi reduzida e não carrega mais os metadados do celular."""
        import io

        from PIL import Image

        hosp_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/prontuario")
        fotos = hosp_page.locator(".anexos-galeria a.anexo-item")
        assert fotos.count() == 2

        fotos.nth(1).click()
        assert hosp_page.locator(".visualizador").is_visible()
        assert "2 de 2" in hosp_page.inner_text(".visualizador-contador")
        hosp_page.keyboard.press("Escape")
        assert hosp_page.locator(".visualizador").is_hidden()

        resp = hosp_page.request.get(servidor + fotos.nth(1).get_attribute("href"))
        assert resp.status == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert "no-store" in resp.headers["cache-control"]
        imagem = Image.open(io.BytesIO(resp.body()))
        assert max(imagem.size) == 2000  # 3000 px reduzido
        assert len(imagem.getexif()) == 0  # metadados descartados

    def test_remover_foto(self, soc_page, servidor, contexto):
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/pacientes")
        soc_page.click('a:has-text("Prontuário Médico")')
        soc_page.wait_for_load_state("networkidle")
        soc_page.locator('input[name="remover_anexo"]').first.check()
        soc_page.click('button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        soc_page.click('a:has-text("Prontuário Médico")')
        soc_page.wait_for_load_state("networkidle")
        assert soc_page.locator(".anexo-existente").count() == 1

    @pytest.mark.regra("RN-007")
    def test_hospital_acompanha_o_prontuario(self, hosp_page, servidor, contexto):
        hosp_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/prontuario")
        texto = hosp_page.inner_text("body")

        assert "Maria Teste" in texto
        assert "Suspeita de síndrome coronariana aguda." in texto

    def test_finalizar_sem_chegada_e_impossivel(self, soc_page, servidor, contexto):
        """Antes de confirmar a chegada, o formulário de finalizar nem existe."""
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}")
        soc_page.wait_for_load_state("networkidle")

        assert soc_page.locator(".finalizar-form").count() == 0
        assert soc_page.locator("#form-notificar-chegada").is_hidden()

    @pytest.mark.regra("HU-021")
    def test_notificar_chegada_longe_do_hospital_e_rejeitado(self, soc_page, contexto):
        """Forçando o botão escondido, o servidor recusa: a ~400 m ainda está
        fora do raio de tolerância de 200 m."""
        soc_page.evaluate("document.getElementById('form-notificar-chegada').hidden = false")
        soc_page.click('#form-notificar-chegada button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "Não foi possível notificar chegada" in texto_flash(soc_page)
        assert soc_page.locator(".finalizar-form").count() == 0

    @pytest.mark.regra("HU-021", "HU-022")
    @pytest.mark.eventos_ws("localizacao_atualizada", "trajeto_concluido", "socorrista_chegou")
    def test_trajeto_e_notificacao_de_chegada(self, soc_page, hosp_page, servidor, contexto, db_app):
        """O servidor move o veículo pela rota; ao fim do trajeto o botão de
        chegada aparece e o hospital é avisado em tempo real."""
        hosp_page.goto(f"{servidor}/ocorrencias/{contexto['id']}")
        hosp_page.wait_for_load_state("networkidle")

        soc_page.click("#btn-iniciar-trajeto")
        soc_page.wait_for_function("document.getElementById('form-voltar-hospitais').hidden", timeout=5000)
        resp = soc_page.request.post(f"{servidor}/ocorrencias/{contexto['id']}/trocar-hospital")
        assert resp.url.endswith(f"/ocorrencias/{contexto['id']}")  # recusado: volta pra ocorrência
        assert _ocorrencia(contexto).hospital_id is not None
        soc_page.wait_for_function(
            "document.getElementById('btn-iniciar-trajeto').textContent.includes('Trajeto concluído')",
            timeout=150000,
        )
        assert soc_page.locator("#form-notificar-chegada").is_visible()
        soc_page.click('#form-notificar-chegada button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "Chegada notificada com sucesso!" in texto_flash(soc_page)
        assert soc_page.locator(".finalizar-form").count() == 1
        esperar_aviso(hosp_page, "O socorrista já chegou ao seu destino!")

    def test_finalizar_sem_desfecho_e_rejeitado_pelo_servidor(self, soc_page):
        desligar_validacao_html(soc_page)
        soc_page.click('.finalizar-form button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "O campo desfecho é obrigatório." in texto_flash(soc_page)

    @pytest.mark.regra("RN-023")
    @pytest.mark.eventos_ws("ocorrencia_finalizada")
    def test_finalizar_e_ver_relatorio(self, soc_page, hosp_page, contexto, db_app):
        soc_page.fill("#desfecho", "Paciente atendida e encaminhada, quadro estável na chegada.")
        soc_page.click('.finalizar-form button[type="submit"]')
        soc_page.wait_for_load_state("networkidle")

        assert "Ocorrência finalizada com sucesso!" in texto_flash(soc_page)
        assert _ocorrencia(contexto).status.value == "finalizada"
        esperar_aviso(hosp_page, "Ocorrência finalizada.")

        soc_page.click('a:has-text("Ver relatório final")')
        soc_page.wait_for_load_state("networkidle")
        texto = soc_page.inner_text(".relatorio-card")
        assert "Maria Teste" in texto
        assert "Hospital de Base do Distrito Federal" in texto
        assert "CPF: None" not in texto  # regressão do mesmo bug

    @pytest.mark.regra("RN-022")
    def test_chat_vira_somente_leitura_apos_finalizar(self, soc_page, servidor, contexto):
        soc_page.goto(f"{servidor}/ocorrencias/{contexto['id']}")

        assert soc_page.locator("#chat-form").count() == 0
        assert soc_page.locator('a:has-text("Ver histórico do chat")').count() == 1

    def test_inbox_do_socorrista(self, soc_page, servidor, contexto):
        soc_page.goto(f"{servidor}/inbox/")
        assert "Hospital de Base do Distrito Federal" in soc_page.inner_text("body")

        soc_page.click(f'a[href="/inbox/{contexto["id"]}"]')
        soc_page.wait_for_function(
            "document.getElementById('chat-mensagens').innerText.includes('Leito de emergência')",
            timeout=5000,
        )
        assert "A caminho com paciente" in soc_page.inner_text("#chat-mensagens")

    def test_socorrista_livre_pode_abrir_nova_ocorrencia(self, soc_page, servidor):
        """Com a anterior finalizada, o dashboard volta pro formulário."""
        soc_page.goto(f"{servidor}/dashboard")
        soc_page.wait_for_load_state("networkidle")

        assert "/ocorrencias/novo" in soc_page.url

    def test_historico_do_hospital(self, hosp_page, servidor, contexto):
        hosp_page.goto(f"{servidor}/emergencias/historico")
        texto = hosp_page.inner_text("body")

        assert f"EMG-{contexto['id']:04d}" in texto
        assert "Ana Souza" in texto

    def test_horarios_no_fuso_de_brasilia(self, hosp_page, servidor, contexto, db_app, tmp_path):
        """REGRESSÃO: o banco guarda UTC e o histórico, o relatório e o CSV
        mostravam esse horário cru — 3 horas adiantado em relação a
        Brasília. Agora todos batem com o horário local."""
        from datetime import timezone
        from zoneinfo import ZoneInfo

        ocorrencia = _ocorrencia(contexto)
        def local(momento):
            return (momento.replace(tzinfo=timezone.utc)
                    .astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M"))
        inicio, fim = local(ocorrencia.criado_em), local(ocorrencia.finalizado_em)

        hosp_page.goto(f"{servidor}/emergencias/historico")
        linha = hosp_page.locator("tr", has_text=f"EMG-{contexto['id']:04d}").inner_text()
        assert inicio in linha
        assert fim in linha

        hosp_page.goto(f"{servidor}/ocorrencias/{contexto['id']}/relatorio")
        assert fim in hosp_page.inner_text(".relatorio-card")

        with hosp_page.expect_download() as download_info:
            hosp_page.evaluate(f"window.location.href = '{servidor}/emergencias/historico/exportar'")
        destino = tmp_path / "historico.csv"
        download_info.value.save_as(destino)
        assert f"{inicio};{fim}" in destino.read_text(encoding="utf-8-sig")

    def test_historico_com_filtros(self, hosp_page, servidor, contexto):
        hosp_page.goto(f"{servidor}/emergencias/historico?busca=Ana")
        assert f"EMG-{contexto['id']:04d}" in hosp_page.inner_text("body")

        hosp_page.goto(f"{servidor}/emergencias/historico?busca=NaoExiste")
        assert "Nenhuma emergência encontrada com esses filtros." in hosp_page.inner_text("body")

    def test_exportar_historico_csv(self, hosp_page, servidor, contexto, tmp_path):
        hosp_page.goto(f"{servidor}/emergencias/historico")
        with hosp_page.expect_download() as download_info:
            hosp_page.evaluate(f"window.location.href = '{servidor}/emergencias/historico/exportar'")
        destino = tmp_path / "historico.csv"
        download_info.value.save_as(destino)
        conteudo = destino.read_text(encoding="utf-8-sig")

        assert download_info.value.suggested_filename.startswith("historico-emergencias-")
        assert conteudo.splitlines()[0].startswith("ID;Status;Tipo;Socorrista")
        assert f"EMG-{contexto['id']:04d};Finalizada" in conteudo

    def test_inbox_do_hospital(self, hosp_page, servidor, contexto):
        hosp_page.goto(f"{servidor}/inbox/{contexto['id']}")
        hosp_page.wait_for_function(
            "document.getElementById('chat-mensagens').innerText.includes('A caminho com paciente')",
            timeout=5000,
        )

        assert "Ana Souza" in hosp_page.inner_text("body")
        assert hosp_page.get_attribute("a.inbox-telefone-btn", "href") == "tel:(61) 99876-5432"

    def test_logout_socorrista_e_hospital(self, soc_page, hosp_page, servidor):
        soc_page.goto(f"{servidor}/logout")
        hosp_page.goto(f"{servidor}/logout")

        assert "/login" in soc_page.url
        assert "/login" in hosp_page.url
