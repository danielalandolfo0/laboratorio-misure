# PAPILA: provenienza del CSV incluso

`papila.csv` è stato preparato dai fogli `patient_data_od.xlsx` e
`patient_data_os.xlsx` della raccolta PAPILA mediante
`python/prepara_papila.py`. Contiene una riga per ciascuno dei 244 pazienti
con diagnosi disponibile per entrambi gli occhi. Le fotografie sono mostrate
dal sito tramite la copia pubblica della raccolta su GitHub, con i nomi dei
file indicati nelle colonne `image_OD` e `image_OS`.

Fonte: Kovalyk O., Morales-Sánchez J., Verdú-Monedero R., Sellés-Navarro I.,
Palazón-Cabanes A., Sancho-Gómez J.-L. (2022), *PAPILA: Dataset with fundus
images and clinical data of both eyes of the same patient for glaucoma
assessment*, Scientific Data 9, 291,
https://doi.org/10.1038/s41597-022-01388-1.

Raccolta originale: https://doi.org/10.6084/m9.figshare.14798004.v2.
Licenza dei dati: GNU GPL 3.0 o successiva, come riportato nella scheda
Figshare. Copia pubblica delle immagini usata dal sito:
https://github.com/JuanitoOrtega/papila_db/tree/main/DB_PAPILA/FundusImages.

La trasformazione conserva separatamente i campi OD e OS, inclusi quelli
discordanti fra i due fogli, e non usa le diagnosi nei confronti.
