# Isometrisch Langlingen

Langlingen, an der Aller im Landkreis Celle, als isometrische Pixelkarte. Der Renderer und der Aufbau der Pipeline stammen von [Isometric Helenaveen](https://github.com/jankeesvw/isometric-helenaveen) von [@jankeesvw](https://github.com/jankeesvw). Diese Fassung tauscht die niederländischen Quellen gegen die offenen Geodaten Niedersachsens.

Das Gebiet ist 2,5 × 2,5 km um die Kirche St. Johannis, in ETRS89 / UTM Zone 32N (EPSG:25832): von 586000 / 5822500 bis 588500 / 5825000.

## Daten und Lizenzen

- **Gebäude, LoD2** (CityGML, AdV): [LGLN](https://lod.stac.lgln.niedersachsen.de), CC BY 4.0. Das steht so in jeder Datei (`Lizenz: CC-BY-4.0`). Das STAC-Feld der Sammlung sagt nur „various“.
- **Gelände, DGM1**, und **Oberfläche, DOM1**, je 1 m, hier auf 0,5 m gebracht: LGLN, [CC BY 4.0](https://dgm.stac.lgln.niedersachsen.de/collections/dgm1).
- **Luftbild DOP20**: LGLN, [CC BY 4.0](https://dop.stac.lgln.niedersachsen.de/collections/DOP), bezogen über den WMS `ni_dop20`.
- **Straßen, Wasser, Wege, Orte, Verkehr**: © [OpenStreetMap](https://www.openstreetmap.org/copyright)-Mitwirkende, ODbL.
- **Fotos der Rundfahrt**: Wikimedia Commons. St. Johannis und das Rittergut von Clemensfranz, CC BY-SA 3.0; die zweite Kirchenansicht von ClausNe, CC BY-SA 4.0.

Quellenangabe, wie sie das LGLN verlangt: Quelle: © LGLN (2026), CC BY 4.0.

Der Boden wird aus OpenStreetMap in die Layer gemalt, die der niederländische Maler schon kennt (Wiese, Acker, Wald, Asphalt, Wasser). Es gibt hier kein BGT. Die Dächer kommen aus dem LoD2, nicht aus einer geschätzten Höhe.

## Bauen

```sh
./build.sh
python3 -m http.server 8000 -d site
```

`uv` holt dafür Python 3.12. Außerdem braucht es Node, vips und ImageMagick. `./deploy.sh` legt `site/` auf den Branch `gh-pages`.

Die Geschichten in `scripts/landmarks.py` und `scripts/build_history.py` sind die öffentlichen: Kirche, Gut, die datierten Fachwerkhäuser, die Bahn bis 1981. Was nur im Dorf bekannt ist, steht dort nicht.
