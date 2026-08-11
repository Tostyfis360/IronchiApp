# Empleo Tenerife

Buscador automático de ofertas de empleo en **La Laguna** y **Santa Cruz de
Tenerife**, en dos categorías: **moda/retail** y **comunicación audiovisual**.
Rastrea InfoJobs, Job Today, Indeed (best-effort), Mango, RTVC y Jooble dos
veces al día, filtra por categoría/marca/ciudad/jornada, y publica los
resultados en una web estática gratis con GitHub Pages.

## Cómo funciona

- `scraper/` — script en Python que consulta cada fuente, descarta lo que no
  encaja (marcas excluidas, fuera de zona, no relacionado con ninguna
  categoría configurada), puntúa cada oferta y guarda el resultado en
  `docs/data/jobs.json`.
- `docs/` — la web (HTML/CSS/JS sin dependencias) que lee ese JSON. Esta
  carpeta es la que sirve GitHub Pages.
- `.github/workflows/scrape.yml` — ejecuta el scraper automáticamente dos
  veces al día (mañana y tarde) y commitea los datos actualizados.

Para ajustar categorías, marcas/empresas, ciudades o palabras clave, edita
[`scraper/config.yaml`](scraper/config.yaml) — no hace falta tocar el código.
Cada categoría (`categories.moda`, `categories.audiovisual`) es un bloque
independiente; añadir una tercera categoría es solo copiar el bloque y
rellenarlo.

## Puesta en marcha (una sola vez)

1. **Hacer el repositorio público**: Settings → General → Danger Zone →
   Change visibility → Public. (Necesario para que GitHub Pages y las
   Actions sean gratis sin límite de minutos.)

2. **Activar GitHub Pages**: Settings → Pages → Build and deployment →
   Source: "Deploy from a branch" → Branch: `main`, carpeta `/docs` → Save.
   La web quedará en `https://<tu-usuario>.github.io/IronchiApp/`.

3. **(Opcional pero recomendado) Clave de Jooble**: es la fuente más fiable.
   Pide una clave gratis en <https://es.jooble.org/api/about> (formulario
   con nombre, email, etc. — te la mandan por correo). Luego en el repo:
   Settings → Secrets and variables → Actions → New repository secret →
   nombre `JOOBLE_API_KEY`, valor la clave recibida. Sin esta clave el resto
   de fuentes funcionan igual, simplemente no se consulta Jooble.

4. **Lanzar la primera ejecución manual**: pestaña Actions → "Actualizar
   ofertas de empleo" → Run workflow. Tras 1-2 minutos, la web ya tendrá
   datos. A partir de ahí se ejecuta sola dos veces al día.

## Notas

- Indeed bloquea el scraping agresivamente (Cloudflare); se intenta en cada
  ejecución pero es normal que a menudo no aporte resultados. El resto de
  fuentes no se ven afectadas si esto pasa.
- Las ofertas que dejan de aparecer se retiran automáticamente tras varias
  ejecuciones seguidas sin verse (se consideran cubiertas/caducadas).
- RTVC (`rtvc.es/trabaja-con-nosotros`) se rastrea directamente; los procesos
  marcados "Proceso Cerrado" se descartan automáticamente. Ahora mismo no
  tienen ninguno abierto, pero en cuanto publiquen uno nuevo debería
  aparecer solo, sin tocar nada.
