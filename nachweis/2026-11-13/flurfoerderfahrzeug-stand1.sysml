// Erzeugt von der Bausteinbrücke aus den Bausteinbeschreibungen; nicht von Hand ändern.
package Flurfoerderfahrzeug {
    private import ScalarValues::*;
    metadata def Herkunft { attribute bausteinId : String; attribute version : String; attribute ebene : String; attribute vorgaenger : String; }
    metadata def Semantik { attribute begriff : String; attribute iri : String; }
    port def Datenport;
    port def Energieport;
    port def Steuerport;
    package Anforderungen {
        requirement <'R-20'> fahrgeschwindigkeit { doc /* Das Fahrzeug fährt im Automatikbetrieb höchstens 1,5 m/s. */ }
        requirement <'R-21'> personenschutz { doc /* Personen im Fahrweg werden erkannt; das Fahrzeug hält vorher an. */ }
        requirement <'R-22'> leitsystem { doc /* Das Fahrzeug empfängt Fahraufträge und meldet seinen Zustand. */ }
    }
    package Funktionen {
        action <'F-FF-02'> fahren { doc /* Fahrzeug entlang der Route bewegen */ }
        action <'F-FF-03'> hindernisErkennen { doc /* Hindernisse und Personen im Fahrweg erkennen */ }
        action <'F-FF-01'> navigieren { doc /* Position bestimmen und Route planen */ }
        action <'F-FF-04'> kommunizieren { doc /* Fahraufträge empfangen und Zustand melden */ }
    }
    state def AntriebseinheitZustaende {
        entry; then stillstand;
        state stillstand;
        state fahrt;
        state notHalt { doc /* Bedingung (informell): sofort, wenn die Sicherheitssteuerung abschaltet */ }
    }
    state def SicherheitslaserscannerZustaende {
        entry; then frei;
        state frei;
        state warnfeldVerletzt;
        state schutzfeldVerletzt;
    }
    state def NavigationsrechnerZustaende {
        entry; then hochfahren;
        state hochfahren;
        state bereit;
        state auftragAktiv;
    }
    part def <'B-AE'> Antriebseinheit {
        metadata Herkunft { bausteinId = "B-AE"; version = "1.1.0"; ebene = "P"; vorgaenger = ""; }
        metadata Semantik { begriff = "Antrieb"; iri = "https://example.org/bausteine/begriff/Antrieb"; }
        doc /* Zwei Antriebsräder mit Motoren und Bremsen. */
        attribute maxGeschwindigkeit :> ISQ::speed = 1.5 [SI::m/SI::s];
        attribute nennspannung :> ISQ::electricPotentialDifference = 48 [SI::V];
        port steuerung : Steuerport;
        port versorgung : Energieport;
        exhibit state betrieb : AntriebseinheitZustaende;
    }
    part def <'B-LS'> Sicherheitslaserscanner {
        metadata Herkunft { bausteinId = "B-LS"; version = "1.0.0"; ebene = "P"; vorgaenger = ""; }
        metadata Semantik { begriff = "Schutzfeldsensor"; iri = "https://example.org/bausteine/begriff/Schutzfeldsensor"; }
        doc /* Überwacht Schutzfelder im Fahrweg. Messgröße: Hindernis im Schutzfeld. */
        attribute reichweite :> ISQ::length = 5500 [SI::mm];
        attribute abtastrate :> ISQ::frequency = 25 [SI::Hz];
        port meldung : Datenport;
        exhibit state betrieb : SicherheitslaserscannerZustaende;
    }
    part def <'B-NR'> Navigationsrechner {
        metadata Herkunft { bausteinId = "B-NR"; version = "3.2.0"; ebene = "L"; vorgaenger = ""; }
        metadata Semantik { begriff = "Steuerrechner"; iri = "https://example.org/bausteine/begriff/Steuerrechner"; }
        doc /* Rechner für Lokalisierung, Routenplanung und Leitsystemanbindung. */
        attribute zykluszeit :> ISQ::time = 0.05 [SI::s];
        attribute betriebssystem : String = "Linux";
        port leitsystem : Datenport;
        port fahrbefehl : Steuerport;
        exhibit state betrieb : NavigationsrechnerZustaende;
    }
    part flurfoerderfahrzeug {
        part antriebseinheit : Antriebseinheit;
        part sicherheitslaserscanner : Sicherheitslaserscanner;
        part navigationsrechner : Navigationsrechner;
    }
    satisfy Anforderungen::fahrgeschwindigkeit by flurfoerderfahrzeug.antriebseinheit;
    satisfy Anforderungen::personenschutz by flurfoerderfahrzeug.sicherheitslaserscanner;
    satisfy Anforderungen::leitsystem by flurfoerderfahrzeug.navigationsrechner;
    allocate Funktionen::fahren to flurfoerderfahrzeug.antriebseinheit;
    allocate Funktionen::hindernisErkennen to flurfoerderfahrzeug.sicherheitslaserscanner;
    allocate Funktionen::navigieren to flurfoerderfahrzeug.navigationsrechner;
    allocate Funktionen::kommunizieren to flurfoerderfahrzeug.navigationsrechner;
}
