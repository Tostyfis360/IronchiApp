# Empleo Moda Tenerife

Buscador automático de ofertas de dependienta/o en moda en **La Laguna** y
**Santa Cruz de Tenerife**. Rastrea InfoJobs, Job Today, Indeed (best-effort),
Mango y Jooble dos veces al día, filtra por marca/ciudad/jornada, y publica
los resultados en una web estática gratis con GitHub Pages.

## Cómo funciona

- `scraper/` — script en Python que consulta cada fuente, descarta lo que no
  encaja (marcas excluidas, fuera de zona, no relacionado con moda/retail),
  puntúa cada oferta y guarda el resultado en `docs/data/jobs.json`.
- `docs/` — la web (HTML/CSS/JS sin dependencias) que lee ese JSON. Esta
  carpeta es la que sirve GitHub Pages.
- `.github/workflows/scrape.yml` — ejecuta el scraper automáticamente dos
  veces al día (mañana y tarde) y commitea los datos actualizados.

Para ajustar marcas, ciudades o palabras clave, edita
[`scraper/config.yaml`](scraper/config.yaml) — no hace falta tocar el código.

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
