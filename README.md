# Isometrisch Müden (Aller)

Ettenbüttel, ein Ortsteil von Müden (Aller) im Landkreis Gifhorn, als isometrische Pixelkarte. Das Blatt liegt um die Grüne Heide. Der Renderer und der Aufbau der Pipeline stammen von [Isometric Helenaveen](https://github.com/jankeesvw/isometric-helenaveen) von [@jankeesvw](https://github.com/jankeesvw). Diese Fassung tauscht die niederländischen Quellen gegen die offenen Geodaten Niedersachsens.

Das Gebiet ist 3,5 × 3,5 km, in ETRS89 / UTM Zone 32N (EPSG:25832): von 595000 / 5815500 bis 598500 / 5819000. Die Karte öffnet am Wohnhaus Grüne Heide 18. Der Kernort Müden, mit St. Petri und der Okermündung, liegt etwa fünf Kilometer nordwestlich und ist nicht auf diesem Blatt.

## Daten und Lizenzen

- **Gebäude, LoD2** (CityGML, AdV): [LGLN](https://lod.stac.lgln.niedersachsen.de), CC BY 4.0. Das steht so in jeder Datei (`Lizenz: CC-BY-4.0`). Das STAC-Feld der Sammlung sagt nur „various“.
- **Gelände, DGM1**, und **Oberfläche, DOM1**, je 1 m, hier auf 0,5 m gebracht: LGLN, [CC BY 4.0](https://dgm.stac.lgln.niedersachsen.de/collections/dgm1).
- **Luftbild DOP20**: LGLN, [CC BY 4.0](https://dop.stac.lgln.niedersachsen.de/collections/DOP), bezogen über den WMS `ni_dop20`.
- **Straßen, Wasser, Wege, Orte, Verkehr**: © [OpenStreetMap](https://www.openstreetmap.org/copyright)-Mitwirkende, ODbL.
- **Fotos der Rundfahrt**: Wikimedia Commons. Die Ortseinfahrt von Kirchenfan, CC0. Allertal 15, Hirtenwinkel 4 und der Speicher in Bokelberge von Simone Thulke, CC BY 4.0.

Quellenangabe, wie sie das LGLN verlangt: Quelle: © LGLN (2026), CC BY 4.0.

Der Boden wird aus OpenStreetMap in die Layer gemalt, die der niederländische Maler schon kennt (Wiese, Acker, Wald, Asphalt, Wasser). Es gibt hier kein BGT. Die Dächer kommen aus dem LoD2, nicht aus einer geschätzten Höhe.

## Bauen

```sh
./build.sh
python3 -m http.server 8000 -d site
```

`uv` holt dafür Python 3.12. Außerdem braucht es Node, vips und ImageMagick. `./deploy.sh` legt `site/` auf den Branch `gh-pages`.

Die Geschichten in `scripts/landmarks.py` und `scripts/build_history.py` sind die öffentlichen: die Eingemeindung 1974, drei eingetragene Fachwerkbauten, die Aller nördlich des Orts. Was nur im Dorf bekannt ist, steht dort nicht.
