# SPDX-License-Identifier: AGPL-3.0-only
import keyring
import pytest
from keyring.backend import KeyringBackend

from kopru import ayarlar
from kopru.ceviri.sahte import SahteMotor


class BellekKasasi(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.veri = {}

    def get_password(self, servis, kullanici):
        return self.veri.get((servis, kullanici))

    def set_password(self, servis, kullanici, parola):
        self.veri[(servis, kullanici)] = parola

    def delete_password(self, servis, kullanici):
        self.veri.pop((servis, kullanici), None)


@pytest.fixture(autouse=True)
def ortam(tmp_path, monkeypatch):
    monkeypatch.setenv("KOPRU_AYAR_DIZINI", str(tmp_path))
    kasa = BellekKasasi()
    onceki = keyring.get_keyring()
    keyring.set_keyring(kasa)
    yield kasa
    keyring.set_keyring(onceki)


@pytest.fixture
def uygulama_ayari():
    return ayarlar.yukle()


def sahte_fabrika(kod, ayar):
    return SahteMotor()


class SahteSurec:
    def __init__(self, cmd):
        self.cmd, self.kapandi, self.cikis = cmd, False, None

    def poll(self):
        return self.cikis

    def terminate(self):
        self.kapandi = True
        self.cikis = -15


@pytest.fixture(autouse=True)
def katman_surec_yok(monkeypatch):
    """Testler gerçek ekran katmanı süreci başlatmasın."""
    from kopru.katman import yonetim
    baslatilanlar = []
    monkeypatch.setattr(yonetim, "surec_baslat", lambda cmd: baslatilanlar.append(SahteSurec(cmd)) or baslatilanlar[-1])
    return baslatilanlar
