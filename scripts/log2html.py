#!/usr/bin/env python3
"""Script converting pyatv logs to HTML."""

import os
import re
import sys
import json
import logging
import argparse

_LOGGER = logging.getLogger(__name__)

# Used by atvremote, atvscript, etc.
LOG_LINE_RE = (
    r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+):(?P<content>.*)"
)

# Used by Home Assistant
HA_LOG_LINE_RE = (
    r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+) \([^)]*\) "
    r"\[(pyatv|homeassistant.components.apple_tv)[^]]*\] (?P<content>.*)"
)

HTML_TEMPLATE = """<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>pyatv log</title>
  <style type="text/css" media="screen">
    .box_log {{
      margin: 3px;
      padding: 2px;
      border-color: #aaaaaa;
      border-radius: 5px;
      border-style: dotted;
      background: #cccccc;
    }}
    .box_log summary {{
      overflow: scroll;
      white-space: wrap;
    }}
    .box_log pre {{
      overflow-x: auto;
    }}
  </style>

  <script>
    var content = {content};
    var text_filter = null;
    var level_checkboxes = [];

    function createEntry(entry) {{
      var outer = document.createElement("div");
      outer.className = "box_log";

      var details = document.createElement("details");
      outer.appendChild(details);

      var summary = document.createElement("summary");
      summary.innerText = entry[0] + " " + entry[2];
      details.appendChild(summary);

      var desc = document.createElement("pre");
      details.appendChild(desc);

      details.addEventListener("toggle", event => {{
        if (details.open) {{
          desc.innerText = entry[3];

        }}
      }});

      return outer;
    }}

    function populate() {{
      entries = document.getElementById("entries")
      entries.innerHTML = "";

      active_levels = new Set();
      for (const checkbox of level_checkboxes) {{
        if (checkbox.checked) {{
          active_levels.add(checkbox.value);
        }}
      }}

      match_regexp = new RegExp(text_filter, "i");
      for (const entry of content) {{
        if ((text_filter == null || match_regexp.test(entry[3])) &&
            active_levels.has(entry[1])) {{
          entries.appendChild(createEntry(entry));
        }}
      }}
    }}

    function filterText() {{
      text_filter = document.getElementById("filter").value;
      populate();
    }}

    function loadData() {{
      var log_levels = new Set();

      for (const entry of content) {{
        log_levels.add(entry[1]);
      }}

      for (const level of log_levels) {{
        var outer = document.createElement("div");
        outer.style = "display: inline";

        var filter_box = document.createElement("input");
        filter_box.type = "checkbox";
        filter_box.value = level;
        filter_box.id = "LEVEL_" + level;
        filter_box.value = level;
        filter_box.checked = true;
        filter_box.addEventListener('change', (event) => {{
          populate();
        }});

        outer.appendChild(filter_box);
        level_checkboxes.push(filter_box);

        var label = document.createElement("label");
        label.innerText = level;
        label.for = "LEVEL_" + level;
        outer.appendChild(label);

        document.getElementById("filters").appendChild(outer);
      }}

      populate();
    }}

    // onload does not seem to work nicely with htmlpreview, so this is a workaround
    var checkExist = setInterval(function() {{
      if (document.getElementById("entries")) {{
        loadData();
        clearInterval(checkExist);
      }}
    }}, 100);
  </script>

</head>
<body>
  <div id="filters" style="display: inline">
    <input type="text" id="filter" onkeyup="filterText()"
           placeholder="Filter regexp..." />
  </div>
  <div id="entries" />
</body>
"""


def parse_logs(stream):
    """Parse lines in a log and return entries."""

    def _match_log_patterns(line):
        for pattern in [LOG_LINE_RE, HA_LOG_LINE_RE]:
            match = re.match(pattern, line)
            if match:
                return match
        return None

    current_date = None
    currenf_level = None
    current_first_line = None
    current_content = ""

    for line in stream:
        match = _match_log_patterns(line)
        if not match:
            current_content += line
            continue

        if current_date:
            yield current_date, currenf_level, current_first_line, current_content

        current_date = match.group("date")
        currenf_level = match.group("level")
        current_content = match.group("content")
        current_first_line = current_content
        current_content += "\n"

    if current_date:
        yield current_date, currenf_level, current_first_line, current_content


def generate_log_page(stream, output):
    """Generate HTML output for log output."""
    logs = list(parse_logs(stream))

    if not logs:
        _LOGGER.warning("No log points found, not generating output")
        return

    page = HTML_TEMPLATE.format(content=json.dumps(logs))
    if not output:
        print(page)
    else:
        with open(output, "w") as out:
            out.write(page)


def main():
    """Script starts here."""

    def _markdown_parser(stream):
        """Look for markup start and end in input.

        This will look for input between tags looking like this:

        ```log

        ```
        """
        found = False
        for line in stream:
            if line.startswith("```log"):
                found = True
            elif line.startswith("```"):
                break
            elif found:
                yield line

    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="log file")
    parser.add_argument("-o", "--output", default=None, help="output file")
    parser.add_argument(
        "-f",
        "--format",
        default="plain",
        choices=["plain", "markdown"],
        help="input format",
    )
    parser.add_argument(
        "-e",
        "--env",
        default=False,
        action="store_true",
        help="read from environment variable",
    )
    args = parser.parse_args()

    def _generate_log(log):
        generate_log_page(
            _markdown_parser(log) if args.format == "markdown" else log, args.output
        )

    if args.env:
        _generate_log(os.environ[args.file].splitlines())
    elif args.file == "-":
        _generate_log(sys.stdin)
    else:
        with open(args.file) as stream:
            _generate_log(stream)


if __name__ == "__main__":
    main()
