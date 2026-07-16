# Anleitung für die API-KI: Navigator-2-IP-Cookies sauber in `idm-heatpump-api` lösen

## Kurzantwort zur bisherigen Integration-Änderung

Ja, in der Home-Assistant-Integration wurde bereits ein Workaround eingebaut: Wenn die installierte `idm-heatpump-api` beim optionalen Webclient einen `session`-Parameter unterstützt, erzeugt die Integration für numerische IP-Hosts eine eigene `aiohttp.ClientSession` mit `aiohttp.CookieJar(unsafe=True)` und übergibt sie an die API.

Das ist aber nur die Integrationsseite. Die sauberere Lösung gehört zusätzlich in die API selbst, weil der Navigator-2-Webclient dort intern die HTTP-Session erzeugt. Dann profitieren auch andere Nutzer der API davon und die Home-Assistant-Integration muss keine Session-Details kennen.

## Ziel für den API-PR

Der `idm-heatpump-api`-Navigator-2-Webclient soll bei intern erzeugten `aiohttp.ClientSession`-Objekten IP-Cookies korrekt akzeptieren, wenn der Zielhost eine numerische IPv4- oder IPv6-Adresse ist.

Der Fix darf nur das lokale Navigator-Weblogin betreffen. Er darf keine Modbus-Register schreiben, keine Wärmepumpenparameter verändern und kein Cloud-Verhalten einführen.

## Fachlicher Hintergrund

Navigator 2.0 verwendet für das lokale Webinterface ein HTTP-/Cookie-basiertes Login. `aiohttp.CookieJar` lehnt Cookies von IP-Adressen standardmäßig ab, weil das aus Browser-/RFC-Sicht restriktiver ist. Bei lokalen Geräten wird aber häufig direkt eine IP-Adresse verwendet, zum Beispiel `192.168.1.50`.

Wenn der Navigator-2-Webclient intern eine Standard-Session erzeugt:

```python
self._session = aiohttp.ClientSession()
```

kann das Login bei direkten IP-Hosts fehlschlagen oder Folge-Requests verlieren den Login-Cookie.

Die Zieländerung ist sinngemäß:

```python
is_ip_host = is_ip_literal(host)
cookie_jar = aiohttp.CookieJar(unsafe=is_ip_host)
self._session = aiohttp.ClientSession(cookie_jar=cookie_jar)
```

Für Hostnamen wie `idm-navigator.local` soll `unsafe=False` bleiben.

## Konkrete Coding-Anweisung für die API-KI

Bitte im Repository `Xerolux/idm-heatpump-api` folgendes umsetzen:

1. Finde den Navigator-2-Webclient bzw. den Codepfad, der für Navigator 2.0 eine interne `aiohttp.ClientSession` erzeugt.
2. Ergänze eine kleine Hilfsfunktion zur Erkennung numerischer IP-Hosts.
   - Nutze die Standardbibliothek `ipaddress`.
   - Unterstütze IPv4, IPv6 und optional Hoststrings mit Port.
   - Unterstütze IPv6 in eckigen Klammern, z. B. `[2001:db8::1]`.
   - Behandle Hostnamen unverändert als nicht unsicher.
3. Wenn der Navigator-2-Webclient selbst eine Session erzeugt, verwende:
   - `aiohttp.CookieJar(unsafe=True)` nur für IP-Literale.
   - `aiohttp.CookieJar(unsafe=False)` oder den Standard für Hostnamen.
4. Wenn dem Webclient bereits eine externe Session übergeben wird, darf die API diese Session nicht überschreiben und nicht schließen, außer das bestehende Ownership-Modell verlangt das bereits ausdrücklich.
5. Behalte die öffentliche API möglichst rückwärtskompatibel.
6. Schreibe Tests, die mindestens diese Fälle abdecken:
   - IPv4-Host erzeugt eine CookieJar mit `unsafe=True`.
   - IPv4-Host mit Port wird korrekt erkannt.
   - IPv6-Host wird korrekt erkannt.
   - IPv6-Host in eckigen Klammern wird korrekt erkannt.
   - Hostname bzw. `.local` erzeugt keine unsichere CookieJar.
   - Extern übergebene Session wird nicht ersetzt.
7. Dokumentiere im Changelog oder in den Release Notes kurz, dass Navigator-2-Weblogin über direkte IP-Adressen stabilisiert wurde.

## Beispiel-Implementierungsskizze

Die tatsächlichen Datei- und Klassennamen bitte an das API-Repository anpassen.

```python
from __future__ import annotations

import ipaddress

import aiohttp


def _is_ip_literal(host: str) -> bool:
    candidate = host.strip()
    if not candidate:
        return False

    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif ":" in candidate and candidate.count(":") == 1:
        # IPv4/Hostname mit Port, z. B. 192.168.1.50:80
        candidate = candidate.rsplit(":", 1)[0]

    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


class Navigator2WebClient:
    def __init__(self, host: str, pin: str, session: aiohttp.ClientSession | None = None) -> None:
        self._host = host
        self._pin = pin
        self._owns_session = session is None

        if session is None:
            cookie_jar = aiohttp.CookieJar(unsafe=_is_ip_literal(host))
            self._session = aiohttp.ClientSession(cookie_jar=cookie_jar)
        else:
            self._session = session
```

## Test-Skizze

Die Tests sollen keine echte Wärmepumpe, kein echtes Netzwerk und keine Modbus-Verbindung benötigen. Falls `aiohttp.CookieJar.unsafe` nicht öffentlich abrufbar ist, bitte `aiohttp.CookieJar` oder `aiohttp.ClientSession` per Monkeypatch/Fake ersetzen und den übergebenen Wert prüfen.

```python
def test_is_ip_literal_detects_ip_hosts() -> None:
    assert _is_ip_literal("192.168.1.50")
    assert _is_ip_literal("192.168.1.50:80")
    assert _is_ip_literal("2001:db8::1")
    assert _is_ip_literal("[2001:db8::1]")
    assert not _is_ip_literal("idm-navigator.local")


def test_internal_session_uses_unsafe_cookie_jar_for_ip(monkeypatch) -> None:
    created_cookie_jars = []

    class FakeCookieJar:
        def __init__(self, *, unsafe: bool = False) -> None:
            self.unsafe = unsafe
            created_cookie_jars.append(self)

    class FakeClientSession:
        def __init__(self, *, cookie_jar) -> None:
            self.cookie_jar = cookie_jar

    monkeypatch.setattr(aiohttp, "CookieJar", FakeCookieJar)
    monkeypatch.setattr(aiohttp, "ClientSession", FakeClientSession)

    Navigator2WebClient("192.168.1.50", "1234")

    assert created_cookie_jars[0].unsafe is True
```

## Akzeptanzkriterien

- Navigator-2-Weblogin funktioniert lokal auch, wenn der Host als direkte IP-Adresse konfiguriert ist.
- Hostnamen behalten das sichere Standardverhalten.
- Keine Modbus-Schreiboperationen werden hinzugefügt.
- Keine Cloud-Aufrufe werden eingeführt.
- Bestehende API-Nutzer mit eigener Session bleiben kompatibel.
- Tests für IP- und Hostname-Fälle sind vorhanden.

## Hinweis zur Home-Assistant-Integration

Nach dem API-Release sollte die Home-Assistant-Integration auf die neue `idm-heatpump-api`-Version gepinnt werden. Danach kann geprüft werden, ob der Integrations-Workaround noch nötig ist oder ob die Session-Erzeugung vollständig der API überlassen werden kann.
