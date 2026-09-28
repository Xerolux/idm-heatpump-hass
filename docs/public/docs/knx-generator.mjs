/* Interactive KNX group address generator for the documentation site.
   Renders itself into <div data-knx-generator></div>; every other page that
   includes this module does nothing. The UI language follows the page
   language (the build sets <html lang> per language variant). All heavy
   lifting lives in knx-generator-core.mjs, which the Node parity harness
   keeps byte-compatible with the command-line generator. */

import * as core from "./knx-generator-core.mjs";

const STRINGS = {
  de: {
    baseLabel: "Basisgruppenadresse",
    baseHelp: "Muss mit der Basis-Gruppenadresse in der Konfiguration der KNX-Bridge übereinstimmen.",
    invalidFormat: "Keine gültige Gruppenadresse — erwartet wird z. B. 8/0/0, 11/0/0 oder 8/1.",
    outOfRange: "Die Adresse liegt außerhalb des KNX-Adressraums.",
    broadcast: "0/0/0 ist für den Broadcast reserviert und kann keine Basis sein.",
    noHeadroom: "Nach dieser Basisadresse bleibt nicht genug Platz für die 999 Objekte des Katalogs.",
    presetLegend: "Vorlage",
    presetCompact: "Kompakt",
    presetFull: "Vollständiger Katalog",
    presetCustom: "Eigene Auswahl",
    groupsLegend: "Objektgruppen",
    summary: (count, first, last) =>
      `${count} Objekte · Gruppenadressen ${first} – ${last} · etwa ${count} Telegramme beim ersten Export`,
    previewSummary: (count) => `Vorschau (${count} Objekte)`,
    colName: "Name",
    colObject: "Objekt",
    colAddress: "Gruppenadresse",
    colDpt: "DPT",
    colDirection: "Richtung",
    directionRead: "lesen",
    directionWrite: "lesen/schreiben",
    downloadXml: "ETS-Importdatei herunterladen (.xml)",
    downloadCsv: "Referenztabelle herunterladen (.csv)",
    emptySelection: "Nichts ausgewählt — mindestens eine Objektgruppe oder eine Vorlage wählen.",
    loadError: "Der Objektkatalog konnte nicht geladen werden. Die Seite bitte neu laden oder über GitHub melden.",
  },
  en: {
    baseLabel: "Base group address",
    baseHelp: "Must match the base group address configured in the KNX bridge options.",
    invalidFormat: "Not a valid group address — expected something like 8/0/0, 11/0/0 or 8/1.",
    outOfRange: "The address is outside the KNX address space.",
    broadcast: "0/0/0 is reserved for broadcast and cannot be a base.",
    noHeadroom: "This base address leaves less room than the catalogue's 999 objects need.",
    presetLegend: "Preset",
    presetCompact: "Compact",
    presetFull: "Full catalogue",
    presetCustom: "Custom selection",
    groupsLegend: "Object groups",
    summary: (count, first, last) =>
      `${count} objects · group addresses ${first} – ${last} · about ${count} telegrams on first export`,
    previewSummary: (count) => `Preview (${count} objects)`,
    colName: "Name",
    colObject: "Object",
    colAddress: "Group address",
    colDpt: "DPT",
    colDirection: "Direction",
    directionRead: "read",
    directionWrite: "read/write",
    downloadXml: "Download ETS import file (.xml)",
    downloadCsv: "Download reference table (.csv)",
    emptySelection: "Nothing selected — pick at least one object group or a preset.",
    loadError: "The object catalogue could not be loaded. Reload the page or report it on GitHub.",
  },
};

/* English labels for the object groups; the German ones come from the
   catalogue, which names the ETS middle groups in German. */
const GROUP_LABELS_EN = {
  system: "System",
  heat_pump: "Heat pump",
  dhw: "Hot water",
  heating_circuits: "Heating circuits",
  zones: "Zone modules",
  glt: "Building management",
  energy: "Energy",
  solar: "Solar",
  isc: "ISC",
  cascade: "Cascade",
  booster: "Booster",
  pv: "PV & battery",
};

/* The groups the compact preset draws from — a sensible starting point for
   a custom selection. */
const CUSTOM_DEFAULT_GROUPS = ["system", "dhw", "heat_pump", "heating_circuits", "glt", "energy", "pv"];

function text(tag, content, className) {
  const node = document.createElement(tag);
  node.textContent = content;
  if (className) {
    node.className = className;
  }
  return node;
}

function classifyBaseError(message) {
  if (message.startsWith("empty") || message.startsWith("not a group address") || message.startsWith("negative")) {
    return "invalidFormat";
  }
  if (message.includes("reserved for broadcast")) {
    return "broadcast";
  }
  if (message.startsWith("base address")) {
    return "noHeadroom";
  }
  return "outOfRange";
}

function localizeBaseValue(raw) {
  return core.formatGroupAddress(raw);
}

function download(content, filename, type) {
  const blob = new Blob([content], { type });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function buildUi(container, catalog, strings, language) {
  container.replaceChildren();
  container.classList.add("knx-gen");

  const germanLabels = Object.fromEntries(catalog.groups.map((group) => [group.id, group.label]));
  const groupLabel = (id) => (language === "de" ? germanLabels[id] : GROUP_LABELS_EN[id] ?? id);

  /* --- base address -------------------------------------------------- */
  const field = text("div", "", "knx-gen-field");
  const label = document.createElement("label");
  label.htmlFor = "knx-gen-base";
  label.textContent = strings.baseLabel;
  const input = document.createElement("input");
  input.id = "knx-gen-base";
  input.value = catalog.default_base;
  input.autocomplete = "off";
  input.spellcheck = false;
  field.append(label, input, text("p", strings.baseHelp, "knx-gen-help"));
  const error = text("p", "", "knx-gen-error");
  error.hidden = true;
  field.append(error);

  /* --- presets -------------------------------------------------------- */
  const presets = document.createElement("fieldset");
  presets.className = "knx-gen-presets";
  presets.append(text("legend", strings.presetLegend));
  const presetInputs = {};
  for (const [value, labelText] of [
    ["compact", strings.presetCompact],
    ["full", strings.presetFull],
    ["custom", strings.presetCustom],
  ]) {
    const option = document.createElement("label");
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "knx-gen-preset";
    radio.value = value;
    if (value === "compact") {
      radio.checked = true;
    }
    presetInputs[value] = radio;
    option.append(radio, ` ${labelText}`);
    presets.append(option);
  }

  /* --- object groups --------------------------------------------------- */
  const groups = document.createElement("fieldset");
  groups.className = "knx-gen-groups";
  groups.append(text("legend", strings.groupsLegend));
  const groupInputs = {};
  for (const group of catalog.groups) {
    const option = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = group.id;
    checkbox.checked = CUSTOM_DEFAULT_GROUPS.includes(group.id);
    groupInputs[group.id] = checkbox;
    option.append(checkbox, ` ${groupLabel(group.id)} (${group.count})`);
    groups.append(option);
  }

  /* --- summary, preview, actions --------------------------------------- */
  const summary = text("p", "", "knx-gen-summary");
  const preview = document.createElement("details");
  preview.className = "knx-gen-preview";
  const previewSummary = text("summary", strings.previewSummary(0));
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap knx-gen-table";
  preview.append(previewSummary, tableWrap);

  const actions = text("div", "", "knx-gen-actions");
  const xmlButton = document.createElement("button");
  xmlButton.type = "button";
  xmlButton.className = "knx-gen-download";
  xmlButton.textContent = strings.downloadXml;
  const csvButton = document.createElement("button");
  csvButton.type = "button";
  csvButton.className = "knx-gen-download knx-gen-download-secondary";
  csvButton.textContent = strings.downloadCsv;
  actions.append(xmlButton, csvButton);

  container.append(field, presets, groups, summary, preview, actions);

  /* --- state ----------------------------------------------------------- */
  function currentSelection() {
    const preset = Object.values(presetInputs).find((radio) => radio.checked)?.value ?? "compact";
    if (preset === "custom") {
      return { groups: Object.values(groupInputs).filter((box) => box.checked).map((box) => box.value) };
    }
    return { preset };
  }

  function selectedRows() {
    const selection = currentSelection();
    const objects = core.selectObjects(catalog, selection);
    if (!objects.length) {
      return null;
    }
    return core.buildRows(catalog, input.value.trim(), objects);
  }

  function renderPreviewTable(rows) {
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const column of [strings.colName, strings.colObject, strings.colAddress, strings.colDpt, strings.colDirection]) {
      headRow.append(text("th", column));
    }
    head.append(headRow);
    const body = document.createElement("tbody");
    for (const row of rows) {
      const line = document.createElement("tr");
      line.append(
        text("td", row.name),
        text("td", String(row.object)),
        text("td", row.address),
        text("td", row.dptPlain),
        text("td", row.writable ? strings.directionWrite : strings.directionRead)
      );
      body.append(line);
    }
    table.append(head, body);
    tableWrap.replaceChildren(table);
  }

  function update() {
    const groupsEnabled = Object.values(presetInputs).find((radio) => radio.checked)?.value === "custom";
    groups.disabled = !groupsEnabled;

    let baseErrorKey = null;
    try {
      core.validateBaseAddress(input.value);
    } catch (err) {
      baseErrorKey = classifyBaseError(String(err.message));
    }
    if (baseErrorKey) {
      error.textContent = strings[baseErrorKey];
      error.hidden = false;
      input.setAttribute("aria-invalid", "true");
    } else {
      error.hidden = true;
      input.removeAttribute("aria-invalid");
    }

    let rows = null;
    let emptyBySelection = false;
    if (!baseErrorKey) {
      try {
        rows = selectedRows();
      } catch {
        rows = null;
      }
      emptyBySelection = rows === null;
    }

    if (baseErrorKey) {
      summary.textContent = "";
    } else if (emptyBySelection) {
      summary.textContent = strings.emptySelection;
    } else {
      summary.textContent = strings.summary(
        rows.length,
        localizeBaseValue(rows[0].raw),
        localizeBaseValue(rows[rows.length - 1].raw)
      );
    }

    previewSummary.textContent = strings.previewSummary(rows ? rows.length : 0);
    if (rows) {
      renderPreviewTable(rows);
    } else {
      tableWrap.replaceChildren();
    }

    const ready = !baseErrorKey && rows !== null;
    xmlButton.disabled = !ready;
    csvButton.disabled = !ready;

    function triggerDownload(format) {
      let content;
      try {
        content =
          format === "xml"
            ? core.renderXml(rows, { groupLabels: germanLabels })
            : core.renderCsv(rows, { groupLabels: germanLabels });
      } catch {
        return;
      }
      const stem = `idm-waermepumpe-${input.value.trim().replace(/\/+/g, "-")}`;
      download(content, `${stem}.${format}`, format === "xml" ? "application/xml" : "text/csv");
    }

    xmlButton.onclick = () => triggerDownload("xml");
    csvButton.onclick = () => triggerDownload("csv");
  }

  for (const radio of Object.values(presetInputs)) {
    radio.addEventListener("change", update);
  }
  for (const checkbox of Object.values(groupInputs)) {
    checkbox.addEventListener("change", update);
  }
  input.addEventListener("input", update);
  update();
}

function findContainer() {
  return document.querySelector("[data-knx-generator]");
}

/* docs.js owns the article and re-renders it client-side: the server HTML
   is swapped for a loading spinner and then for the rendered markdown, and
   client-side navigation swaps it again later. Any container found early
   can therefore be replaced moments after we built into it. Instead of
   betting on timing, watch the DOM and (re)build into whatever container
   is current whenever mutations settle — building is idempotent, and on
   pages without the placeholder nothing ever happens. */
async function start() {
  const language = document.documentElement.lang === "de" ? "de" : "en";
  const strings = STRINGS[language];

  let catalog = null;
  try {
    /* Cache-bust together with the module itself (?v=<integration version>). */
    const ownQuery = new URL(import.meta.url).search;
    const catalogUrl = new URL(`knx-catalog.json${ownQuery}`, import.meta.url);
    catalog = await (await fetch(catalogUrl)).json();
  } catch {
    const container = findContainer();
    if (container) {
      container.classList.add("knx-gen");
      container.append(text("p", strings.loadError, "knx-gen-error"));
    }
    return;
  }

  let builtInto = null;
  let settleTimer = null;
  const ensureBuilt = () => {
    const container = findContainer();
    if (!container || container === builtInto) {
      return;
    }
    builtInto = container;
    buildUi(container, catalog, strings, language);
  };

  const observer = new MutationObserver(() => {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(ensureBuilt, 120);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  ensureBuilt();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start);
} else {
  start();
}
