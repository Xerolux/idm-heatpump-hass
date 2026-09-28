/* KNX group address generator — pure logic, shared by the browser page and
   the Node parity harness.
   Mirrors scripts/generate_knx_group_addresses.py and the address rules in
   custom_components/idm_heatpump/knx_catalog.py. scripts/check_knx_generator_parity.mjs
   fails the build when the two implementations drift apart, so resist
   changing one without the other. */

export const MAX_OBJECT_NUMBER = 999;
export const MAX_RAW_GROUP_ADDRESS = 65535;

/* Python int() accepts surrounding whitespace and a sign; keep the same
   inputs accepted and rejected. (Python additionally treats "1_0" as 10 —
   nobody types that into a group address field, and the parity harness
   does not cover it.) */
function parsePart(part, address) {
  if (!/^\s*[+-]?\d+\s*$/.test(part)) {
    throw new Error(`not a group address: ${JSON.stringify(address)}`);
  }
  return Number.parseInt(part, 10);
}

export function parseGroupAddress(value) {
  const text = String(value).trim();
  if (!text) {
    throw new Error("empty group address");
  }
  const parts = text.split("/");
  const numbers = parts.map((part) => parsePart(part, value));
  if (numbers.some((number) => number < 0)) {
    throw new Error(`negative group address: ${JSON.stringify(value)}`);
  }

  let raw;
  if (numbers.length === 3) {
    const [main, middle, sub] = numbers;
    if (main > 31 || middle > 7 || sub > 255) {
      throw new Error(`group address out of range: ${JSON.stringify(value)}`);
    }
    raw = (main << 11) + (middle << 8) + sub;
  } else if (numbers.length === 2) {
    const [main, sub] = numbers;
    if (main > 31 || sub > 2047) {
      throw new Error(`group address out of range: ${JSON.stringify(value)}`);
    }
    raw = (main << 11) + sub;
  } else if (numbers.length === 1) {
    raw = numbers[0];
  } else {
    throw new Error(`not a group address: ${JSON.stringify(value)}`);
  }

  if (raw > MAX_RAW_GROUP_ADDRESS) {
    throw new Error(`group address out of range: ${JSON.stringify(value)}`);
  }
  if (raw === 0) {
    throw new Error("0/0/0 is reserved for broadcast");
  }
  return raw;
}

export function validateBaseAddress(value) {
  const raw = parseGroupAddress(value);
  if (raw + MAX_OBJECT_NUMBER > MAX_RAW_GROUP_ADDRESS) {
    throw new Error(
      `base address ${JSON.stringify(value)} leaves less than ${MAX_OBJECT_NUMBER} addresses below the end of the KNX address space`
    );
  }
  return raw;
}

export function formatGroupAddress(raw) {
  if (!(0 < raw && raw <= MAX_RAW_GROUP_ADDRESS)) {
    throw new Error(`group address out of range: ${raw}`);
  }
  return `${(raw >> 11) & 0x1f}/${(raw >> 8) & 0x07}/${raw & 0xff}`;
}

export function dptAttribute(dpt) {
  if (dpt === null || dpt === undefined) {
    return "DPST-1-1";
  }
  const [main, sub] = String(dpt).split(".");
  if (!sub) {
    return `DPT-${Number.parseInt(main, 10)}`;
  }
  return `DPST-${Number.parseInt(main, 10)}-${Number.parseInt(sub, 10)}`;
}

export function selectObjects(catalog, { preset = "full", groups = null } = {}) {
  if (preset === "compact") {
    const wanted = new Set(catalog.compact_registers);
    return catalog.objects.filter((obj) => wanted.has(obj.register));
  }
  if (groups) {
    const known = new Set(catalog.groups.map((group) => group.id));
    const unknown = [...new Set(groups)].filter((group) => !known.has(group)).sort();
    if (unknown.length) {
      throw new Error(`unknown object group(s): ${unknown.join(", ")}`);
    }
    const allowed = new Set(groups);
    return catalog.objects.filter((obj) => allowed.has(obj.group));
  }
  return [...catalog.objects];
}

export function buildRows(catalog, baseAddress, objects, { prefix = "WP" } = {}) {
  const baseRaw = validateBaseAddress(baseAddress);
  const rows = objects.map((obj) => {
    const raw = baseRaw + obj.number;
    return {
      raw,
      address: formatGroupAddress(raw),
      main: (raw >> 11) & 0x1f,
      middle: (raw >> 8) & 0x07,
      name: `${prefix} ${obj.name}`.trim(),
      dpt: dptAttribute(obj.dpt),
      dptPlain: obj.dpt || "1.001",
      object: obj.number,
      register: obj.register,
      group: obj.group,
      writable: obj.writable,
    };
  });
  rows.sort((a, b) => a.raw - b.raw);
  return rows;
}

function middleGroupLabel(entries, groupLabels) {
  const seen = [];
  for (const entry of entries) {
    const label = groupLabels[entry.group] ?? entry.group;
    if (!seen.includes(label)) {
      seen.push(label);
    }
  }
  if (seen.length <= 3) {
    return seen.join(" \u00b7 ");
  }
  const numbers = entries.map((entry) => entry.object);
  return `Objekte ${Math.min(...numbers)}\u2013${Math.max(...numbers)}`;
}

/* Mirrors xml.sax.saxutils.quoteattr: escape the special characters, then
   wrap in double quotes — or single quotes when only those are free. */
function quoteAttr(value) {
  let data = String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\n", "&#10;")
    .replaceAll("\r", "&#13;")
    .replaceAll("\t", "&#9;");
  if (data.includes('"')) {
    if (data.includes("'")) {
      data = `"${data.replaceAll('"', "&quot;")}"`;
    } else {
      data = `'${data}'`;
    }
  } else {
    data = `"${data}"`;
  }
  return data;
}

export function renderXml(rows, { projectName = "Wärmepumpe", groupLabels = {} } = {}) {
  if (!rows.length) {
    throw new Error("nothing selected — no group addresses to write");
  }
  const lines = [
    '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
    '<GroupAddress-Export xmlns="http://knx.org/xml/ga-export/01">',
  ];
  const mains = [...new Set(rows.map((row) => row.main))].sort((a, b) => a - b);
  for (const main of mains) {
    const mainRows = rows.filter((row) => row.main === main);
    const start = Math.max(main * 2048, 1);
    lines.push(
      `  <GroupRange Name=${quoteAttr(projectName)} RangeStart="${start}" RangeEnd="${main * 2048 + 2047}">`
    );
    const middles = [...new Set(mainRows.map((row) => row.middle))].sort((a, b) => a - b);
    for (const middle of middles) {
      const middleRows = mainRows.filter((row) => row.middle === middle);
      const middleStart = Math.max(main * 2048 + middle * 256, 1);
      const label = middleGroupLabel(middleRows, groupLabels);
      lines.push(
        `    <GroupRange Name=${quoteAttr(label)} RangeStart="${middleStart}" RangeEnd="${main * 2048 + middle * 256 + 255}">`
      );
      for (const row of middleRows) {
        lines.push(
          `      <GroupAddress Name=${quoteAttr(row.name)} Address="${row.address}" DPTs="${row.dpt}" />`
        );
      }
      lines.push("    </GroupRange>");
    }
    lines.push("  </GroupRange>");
  }
  lines.push("</GroupAddress-Export>");
  return `${lines.join("\n")}\n`;
}

export function renderCsv(rows, { projectName = "Wärmepumpe", groupLabels = {} } = {}) {
  const lines = ["Hauptgruppe;Mittelgruppe;Gruppenadresse;Name;DPT;IDM-Objekt;Register;Richtung"];
  for (const row of rows) {
    const middle = middleGroupLabel([row], groupLabels);
    const direction = row.writable ? "lesen/schreiben" : "lesen";
    lines.push(
      `${projectName};${middle};${row.address};${row.name};${row.dptPlain};${row.object};${row.register};${direction}`
    );
  }
  return `${lines.join("\n")}\n`;
}
