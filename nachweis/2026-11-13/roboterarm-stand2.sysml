// Erzeugt von der Bausteinbrücke aus den Bausteinbeschreibungen; nicht von Hand ändern.
package Roboterarm {
    private import ScalarValues::*;
    metadata def Herkunft { attribute bausteinId : String; attribute version : String; attribute ebene : String; attribute vorgaenger : String; }
    metadata def Semantik { attribute begriff : String; attribute iri : String; }
    port def Datenport;
    port def Energieport;
    port def Steuerport;
    package Anforderungen {
        requirement <'R-10'> nutzlast { doc /* Der Roboterarm bewegt Teile bis 12 kg. */ }
        requirement <'R-11'> greifkraft { doc /* Der Greifer hält Teile sicher mit mindestens 120 N. */ }
        requirement <'R-13'> bilderkennung { doc /* Teile werden vor dem Greifen optisch erkannt. */ }
    }
    package Funktionen {
        action <'F-RA-01'> gelenkBewegen { doc /* Gelenk auf Sollwinkel bewegen */ }
        action <'F-RA-03'> objektGreifen { doc /* Objekt greifen und halten */ }
        action <'F-RA-02'> teilErkennen { doc /* Teil im Arbeitsbereich erkennen */ }
    }
    state def GelenkantriebZustaende {
        entry; then bereit;
        state bereit;
        state inBewegung;
        state gebremst;
    }
    state def GreifermodulZustaende {
        entry; then offen;
        state offen;
        state geschlossen;
        state stoerung { doc /* Bedingung (informell): Greifkraft nach 2 s nicht erreicht */ }
        state quittiert;
    }
    state def KameramodulZustaende {
        entry; then aus;
        state aus;
        state erfasst;
    }
    part def <'B-GA'> Gelenkantrieb {
        metadata Herkunft { bausteinId = "B-GA"; version = "2.0.0"; ebene = "P"; vorgaenger = ""; }
        metadata Semantik { begriff = "Antrieb"; iri = "https://example.org/bausteine/begriff/Antrieb"; }
        doc /* Servoantrieb mit Getriebe für ein Gelenk des Roboterarms. */
        attribute nennmoment :> ISQ::torque = 12 [SI::N*SI::m];
        attribute maxDrehzahl : Real = 3000 { doc /* Einheit laut Quelle: 1/min */ }
        attribute masse :> ISQ::mass = 1.8 [SI::kg];
        port steuerung : Steuerport;
        port versorgung : Energieport;
        exhibit state betrieb : GelenkantriebZustaende;
    }
    part def <'B-GM'> Greifermodul {
        metadata Herkunft { bausteinId = "B-GM"; version = "1.3.0"; ebene = "P"; vorgaenger = "1.2.0"; }
        metadata Semantik { begriff = "Greifer"; iri = "https://example.org/bausteine/begriff/Greifer"; }
        doc /* Elektrischer Zwei-Finger-Greifer am Handgelenk des Roboterarms. */
        attribute maxGreifkraft :> ISQ::force = 160 [SI::N];
        attribute hub :> ISQ::length = 40 [SI::mm];
        attribute greifzeit :> ISQ::time = 0.35 [SI::s];
        attribute schutzart : String = "IP54";
        port steuerung : Steuerport;
        port versorgung : Energieport;
        exhibit state betrieb : GreifermodulZustaende;
    }
    part def <'B-KM'> Kameramodul {
        metadata Herkunft { bausteinId = "B-KM"; version = "1.0.0"; ebene = "P"; vorgaenger = ""; }
        metadata Semantik { begriff = "Kamera"; iri = "https://example.org/bausteine/begriff/Kamera"; }
        doc /* Kamera über dem Arbeitsbereich zur Teileerkennung. Messgröße: Lage und Art des Teils. */
        attribute bildrate :> ISQ::frequency = 30 [SI::Hz];
        attribute aufloesung : String = "1920 x 1080";
        port bilddaten : Datenport;
        exhibit state betrieb : KameramodulZustaende;
    }
    part roboterarm {
        part gelenkantrieb : Gelenkantrieb;
        part greifermodul : Greifermodul;
        part kameramodul : Kameramodul;
    }
    satisfy Anforderungen::nutzlast by roboterarm.gelenkantrieb;
    satisfy Anforderungen::greifkraft by roboterarm.greifermodul;
    satisfy Anforderungen::bilderkennung by roboterarm.kameramodul;
    allocate Funktionen::gelenkBewegen to roboterarm.gelenkantrieb;
    allocate Funktionen::objektGreifen to roboterarm.greifermodul;
    allocate Funktionen::teilErkennen to roboterarm.kameramodul;
}
