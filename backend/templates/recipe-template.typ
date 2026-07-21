// Recipe layout for Tandoor recipes, adapted from
// https://gist.github.com/AdrianVollmer/07edab2b1fba2747fbf45291ab73d81e
// (itself inspired by https://github.com/maxdinech/typst-recipe)
//
// Unlike the original gist (meant for the `typst compile --input` CLI flow),
// this version takes already-parsed dictionaries/paths as plain function
// arguments - the backend (see backend/app/render.py) writes a small driver
// document per request/job that imports this file and calls recipe_from_json().

#let primary_colour = rgb("#ce1f36")
#let text_colour = rgb("#333")

#let body_font = "Libertinus Serif"
#let title_font = "DejaVu Sans"
#let author_font = "DejaVu Sans"
#let heading_font = "DejaVu Sans"

#let image-height = 15em

// Must match the title column's width in the header grid below (recipe()) -
// used to shrink the title font until it fits on one line.
#let title_column_width = 330pt

// A decimal amount like 0.25 arrives pre-split by the backend (see
// _amount_to_fraction_parts in app/render.py) into whole/num/den parts, so it
// can be rendered as a small nicefrac-style fraction instead of a raw decimal.
#let format_amount(frac) = {
  if frac.whole > 0 and frac.num > 0 {
    [#frac.whole#super[#frac.num]⁄#sub[#frac.den]]
  } else if frac.whole > 0 {
    str(frac.whole)
  } else if frac.num > 0 {
    [#super[#frac.num]⁄#sub[#frac.den]]
  } else {
    ""
  }
}

// Short/abbreviated units (g, kg, ml, l, ...) sit much closer to the amount
// than spelled-out units (Esslöffel, Becher, ...) - a full space reads as too
// loose for e.g. "100 g", so use an eighth-of-an-em space there instead.
#let amount_unit_space(unit) = {
  if unit.len() <= 3 { h(0.125em) } else { " " }
}

#let format_ingredient(ingredient, note_content) = {
  // note_content is precomputed by display_ingredients (see below)
  set list(tight: false)
  set par(spacing: 0.8em, leading: 0.3em)

  if ingredient.is_header {
    return text(fill: primary_colour, font: heading_font, weight: 500, size: 10.5pt, upper(ingredient.food.name))
  }

  let plural = ingredient.amount > 1

  let amount = if ingredient.amount > 0 and not ingredient.no_amount { format_amount(ingredient.amount_frac) } else { "" }
  let unit = if ingredient.unit != none and ingredient.unit.name != "-" {
    if plural and ingredient.unit.plural_name not in (none, "") {
      ingredient.unit.plural_name
    } else {
      ingredient.unit.name
    }
  } else { "" }
  let food = if plural and ingredient.food.plural_name not in (none, "") {
    ingredient.food.plural_name
  } else {
    ingredient.food.name
  }

  if amount != "" and unit != "" {
    [- #amount#amount_unit_space(unit)#unit #food#note_content]
  } else if amount != "" {
    [- #amount #food#note_content]
  } else {
    [- #food#note_content]
  }
}

// Ingredients that share the exact same note text (e.g. several "für Sauce"
// entries) should share a single footnote number instead of getting a fresh
// one each - Typst reuses a footnote's number when it's referenced by label.
// id_prefix keeps label names unique across recipes when several are
// compiled into one document (the collected cookbook PDF).
#let display_ingredients(ingredients, id_prefix) = {
  let seen = (:)
  emph(for ingredient in ingredients {
    let note_content = []
    if ingredient.note not in (none, "") {
      let note = ingredient.note
      if note in seen {
        note_content = footnote(seen.at(note))
      } else {
        let lbl = label(id_prefix + "-fn-note-" + str(seen.len()))
        seen.insert(note, lbl)
        note_content = [#footnote[#note]#lbl]
      }
    }
    format_ingredient(ingredient, note_content)
  })
}

#let display_steps(steps) = {
  [== Zubereitung]
  set par(justify: true)
  set enum(
    spacing: 1em,
    numbering: n => text(fill: primary_colour, font: heading_font, size: 14pt, weight: "bold", str(n)),
  )
  for step in steps {
    enum.item()[
      #if step.name != none and step.name != "" [*#step.name* \ ]
      #step.instruction
      #if step.time > 0 [ _(#step.time min)_]
    ]
  }
}

// Renders each keyword/tag as a small rounded, semi-transparent chip. Plain
// boxes (not a grid/stack) so they wrap onto further lines like inline text
// when there are more tags than fit on one line.
#let display_keywords(keywords) = {
  if keywords.len() == 0 { return [] }
  for kw in keywords {
    box(
      fill: primary_colour.transparentize(50%),
      inset: (x: 6pt, y: 3pt),
      radius: 8pt,
    )[#text(size: 8pt, fill: text_colour, font: heading_font)[#kw.name]]
    h(4pt)
  }
}

#let recipe(
  title: "",
  description: "",
  image_path: none,
  servings: 1,
  servings_text: "",
  working_time: "",
  waiting_time: "",
  ingredients: (),
  steps: (),
  keywords: (),
  source_url: "",
  source_domain: "",
  id_prefix: "r",
  steps_font_size_pt: 11pt,
  print_mode: false,
) = {
  set page(
    margin: (x: 54pt, y: 52pt),
    // Recipe pages themselves never show a visible page number (footer:
    // none below suppresses it), but "numbering" still needs a pattern set -
    // #outline() on the cover page formats each entry's page number using
    // whatever numbering is set on the page it points to, so without this
    // the table of contents would show blank page numbers.
    numbering: "1",
    footer: none,
    fill: if print_mode { none } else { rgb("ede8d0") },
  )
  set text(10pt, font: body_font)

  // Each recipe always fits on a single page (steps_font_size_pt is chosen to
  // guarantee that), so resetting the footnote counter here also resets it
  // per page - otherwise footnote numbers kept climbing across the whole
  // collected book instead of restarting at 1 for each recipe.
  counter(footnote).update(0)

  // A real heading (rather than plain styled text) so the collected
  // cookbook's table of contents (see toc_page below) can find recipe
  // titles via #outline(target: heading.where(level: 1)). The uppercasing
  // happens only here (not in the heading's actual body), so the outline
  // shows the title in normal case - outline entries use the heading's raw
  // body, unaffected by this show rule.
  //
  // Long titles are shrunk until they fit on one line, since the title
  // column has a fixed width and can't wrap onto a second line gracefully.
  show heading.where(level: 1): it => context {
    let shown = upper(it.body)
    let size = 24pt
    let min_size = 13pt
    while size > min_size {
      let w = measure(text(font: title_font, size: size, weight: 200, shown)).width
      if w <= title_column_width { break }
      size -= 0.5pt
    }
    text(fill: primary_colour, font: title_font, size: size, weight: 200, shown)
  }

  show heading.where(level: 2): it => text(
    fill: primary_colour,
    font: heading_font,
    weight: 300,
    size: 11pt,
    grid(
      columns: (auto, auto),
      column-gutter: 5pt,
      [#{ upper(it.body) }],
      [
        #v(5pt)
        #line(length: 100%, stroke: 0.4pt + primary_colour)
      ],
    ),
  )

  grid(
    columns: (title_column_width, 150pt),
    [
      #heading(level: 1)[#title]
      #v(4pt)
      #display_keywords(keywords)
      #v(4pt)
      #emph(description)
    ],
    [
      #v(2pt)
      #set align(right)
      #if working_time != "" [_Zubereitung: #working_time _]
      #if waiting_time != "" [\ _Wartezeit: #waiting_time _]
      #if servings > 0 [\ _Portionen: #servings _]
      #if source_url != "" [\ _Quelle: #link(source_url)[#source_domain]_]
    ],
  )

  if image_path != none {
    context { place(image(image_path, width: page.width, height: image-height), dx: -page.margin.left) }
    v(image-height + 2em)
  }

  grid(
    columns: (140pt, 330pt),
    column-gutter: 15pt,
    [
      #set list(marker: [], body-indent: 0pt)
      #set align(right)
      #text(fill: primary_colour, font: heading_font, weight: 300, size: 11pt, upper([Zutaten\ ]))

      #display_ingredients(ingredients, id_prefix)
    ],
    [
      #set text(size: steps_font_size_pt)
      #display_steps(steps)
    ],
  )
  v(30pt)

  if servings_text != "" {
    // Plain (non-placed) flow content always renders directly above the
    // footnote separator, since Typst appends the footnote area after all
    // normal flow content on the page - no position estimation needed, unlike
    // the earlier place()-based attempts that tried to guess where the
    // footnote area starts.
    align(right)[
      #set text(size: 9pt, fill: text_colour, font: body_font)
      *Benötigtes Geschirr:* #servings_text
    ]
  }
}

// Cover/table-of-contents page for the collected "all recipes" book. Only
// recipe titles (level-1 headings) show up, not the Zutaten/Zubereitung
// sub-headings inside each recipe (those are level 2).
#let toc_page(print_mode: false) = {
  set page(
    margin: (x: 54pt, y: 52pt),
    fill: if print_mode { none } else { rgb("ede8d0") },
    numbering: none,
  )
  align(center + horizon)[
    #text(fill: primary_colour, font: title_font, size: 32pt, weight: 200)[REZEPTSAMMLUNG]
    #v(2em)
    #align(left)[
      #outline(
        title: text(fill: primary_colour, font: heading_font, size: 16pt, weight: 300)[Inhaltsverzeichnis],
        target: heading.where(level: 1),
      )
    ]
  ]
}

#let recipe_from_json(recipe_data, image_path: none, id_prefix: "r", steps_font_size_pt: 11pt, print_mode: false) = {
  let all_ingredients = ()
  for step in recipe_data.steps {
    for ingredient in step.ingredients {
      all_ingredients.push(ingredient)
    }
  }

  let working_time = if recipe_data.working_time > 0 { str(recipe_data.working_time) + " min" } else { "" }
  let waiting_time = if recipe_data.waiting_time > 0 { str(recipe_data.waiting_time) + " min" } else { "" }
  let source_url = if recipe_data.at("source_url", default: none) not in (none, "") { recipe_data.source_url } else { "" }
  let source_domain = if recipe_data.at("source_domain", default: none) not in (none, "") { recipe_data.source_domain } else { "" }
  let keywords = recipe_data.at("keywords", default: ())

  recipe(
    title: recipe_data.name,
    description: recipe_data.description,
    servings: recipe_data.servings,
    servings_text: recipe_data.servings_text,
    working_time: working_time,
    waiting_time: waiting_time,
    ingredients: all_ingredients,
    steps: recipe_data.steps,
    keywords: keywords,
    source_url: source_url,
    source_domain: source_domain,
    image_path: image_path,
    id_prefix: id_prefix,
    steps_font_size_pt: steps_font_size_pt,
    print_mode: print_mode,
  )
}
