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

// Ingredient notes are rendered as our own small superscript-numbered list at
// the bottom of the page (see display_notes) instead of Typst's built-in
// #footnote - that auto-places itself in a dedicated area whose position we
// can't reliably align other content (the "Benötigtes Geschirr" box) against.
#let collect_notes(ingredients) = {
  let notes = ()
  for ingredient in ingredients {
    if ingredient.note not in (none, "") and ingredient.note not in notes {
      notes.push(ingredient.note)
    }
  }
  notes
}

#let format_ingredient(ingredient, note_number) = {
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
  let note_content = if note_number != none { super[#str(note_number)] } else { [] }

  if amount != "" and unit != "" {
    [- #amount#amount_unit_space(unit)#unit #food#note_content]
  } else if amount != "" {
    [- #amount #food#note_content]
  } else {
    [- #food#note_content]
  }
}

#let display_ingredients(ingredients, notes) = {
  emph(for ingredient in ingredients {
    let note_number = if ingredient.note not in (none, "") {
      notes.position(n => n == ingredient.note) + 1
    } else {
      none
    }
    format_ingredient(ingredient, note_number)
  })
}

#let display_notes(notes) = {
  if notes.len() == 0 { return [] }
  set text(size: 8pt, fill: text_colour, font: body_font)
  for (i, note) in notes.enumerate(start: 1) {
    [#super[#str(i)]#h(2pt)#note#h(10pt)]
  }
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
  source_url: "",
  source_domain: "",
  page_number: false,
  steps_font_size_pt: 11pt,
) = {
  set page(
    margin: (x: 54pt, y: 52pt),
    numbering: if page_number { "1" } else { none },
    number-align: right,
    fill: rgb("ede8d0"),
  )
  set text(10pt, font: body_font)

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
    columns: (330pt, 150pt),
    [
      #text(fill: primary_colour, font: title_font, size: 24pt, weight: 200, upper(title))
      #v(0pt)
      #emph(description)
    ],
    [
      #v(2pt)
      #set align(right)
      #if working_time != "" [_Zubereitung: #working_time _]
      #if waiting_time != "" [\ _Wartezeit: #waiting_time _]
      #if servings > 0 [\ _Portionen: #servings _]
      #if source_url != "" [
        \ #text(size: 8.5pt, fill: primary_colour)[_Quelle: #link(source_url)[#source_domain]_]
      ]
    ],
  )

  if image_path != none {
    context { place(image(image_path, width: page.width, height: image-height), dx: -page.margin.left) }
    v(image-height + 2em)
  }

  let notes = collect_notes(ingredients)

  grid(
    columns: (140pt, 330pt),
    column-gutter: 15pt,
    [
      #set list(marker: [], body-indent: 0pt)
      #set align(right)
      #text(fill: primary_colour, font: heading_font, weight: 300, size: 11pt, upper([Zutaten\ ]))

      #display_ingredients(ingredients, notes)
    ],
    [
      #set text(size: steps_font_size_pt)
      #display_steps(steps)
    ],
  )
  v(30pt)

  // Notes list and the "Benötigtes Geschirr" box share one bottom row, so
  // they always start on the same line - the box is right-aligned next to it.
  if notes.len() > 0 or servings_text != "" {
    place(bottom, grid(
      columns: (1fr, auto),
      column-gutter: 10pt,
      align(top + left)[
        #line(length: 100%, stroke: 0.4pt + primary_colour)
        #v(4pt)
        #display_notes(notes)
      ],
      align(top + right)[
        #if servings_text != "" {
          box(
            stroke: 0.6pt + primary_colour,
            inset: 8pt,
            radius: 2pt,
            width: 200pt,
          )[
            #set text(size: 8.5pt, fill: text_colour, font: body_font)
            *Benötigtes Geschirr:* #servings_text
          ]
        }
      ],
    ))
  }
}

#let recipe_from_json(recipe_data, image_path: none, page_number: false, steps_font_size_pt: 11pt) = {
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

  recipe(
    title: recipe_data.name,
    description: recipe_data.description,
    servings: recipe_data.servings,
    servings_text: recipe_data.servings_text,
    working_time: working_time,
    waiting_time: waiting_time,
    ingredients: all_ingredients,
    steps: recipe_data.steps,
    source_url: source_url,
    source_domain: source_domain,
    image_path: image_path,
    page_number: page_number,
    steps_font_size_pt: steps_font_size_pt,
  )
}
