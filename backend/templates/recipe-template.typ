// Recipe layout for Tandoor recipes, adapted from
// https://gist.github.com/AdrianVollmer/07edab2b1fba2747fbf45291ab73d81e
// (itself inspired by https://github.com/maxdinech/typst-recipe)
//
// Unlike the original gist (meant for the `typst compile --input` CLI flow),
// this version takes already-parsed dictionaries/paths as plain function
// arguments, since the browser extension builds the document in-memory via
// typst.ts instead of shelling out to the CLI.

#let primary_colour = rgb("#ce1f36")
#let text_colour = rgb("#333")

#let body_font = "Libertinus Serif"
#let title_font = "DejaVu Sans"
#let author_font = "DejaVu Sans"
#let heading_font = "DejaVu Sans"

#let image-height = 15em

#let format_ingredient(ingredient) = {
  set list(tight: false)
  set par(spacing: 0.8em, leading: 0.3em)

  if ingredient.is_header {
    return text(fill: primary_colour, font: heading_font, weight: 500, size: 10.5pt, upper(ingredient.food.name))
  }

  let amount = if ingredient.amount > 0 and not ingredient.no_amount { str(ingredient.amount) } else { "" }
  let unit = if ingredient.unit != none { ingredient.unit.name } else { "" }
  let food = ingredient.food.name
  let note_text = if ingredient.note != none and ingredient.note != "" { footnote(ingredient.note) } else { "" }

  if amount != "" and unit != "" {
    [- #amount #unit #food#note_text]
  } else if amount != "" {
    [- #amount #food#note_text]
  } else {
    [- #food#note_text]
  }
}

#let display_ingredients(ingredients) = {
  emph(for ingredient in ingredients {
    format_ingredient(ingredient)
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
  page_number: false,
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
    columns: (380pt, 100pt),
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
    ],
  )

  if image_path != none {
    context { place(image(image_path, width: page.width, height: image-height), dx: -page.margin.left) }
    v(image-height + 2em)
  }

  grid(
    columns: (90pt, 380pt),
    column-gutter: 15pt,
    [
      #set list(marker: [], body-indent: 0pt)
      #set align(right)
      #text(fill: primary_colour, font: heading_font, weight: 300, size: 11pt, upper([Zutaten\ ]))
      #[#servings #servings_text]

      #display_ingredients(ingredients)
    ],
    [
      #display_steps(steps)
    ],
  )
  v(30pt)
}

#let recipe_from_json(recipe_data, image_path: none, page_number: false) = {
  let all_ingredients = ()
  for step in recipe_data.steps {
    for ingredient in step.ingredients {
      all_ingredients.push(ingredient)
    }
  }

  let working_time = if recipe_data.working_time > 0 { str(recipe_data.working_time) + " min" } else { "" }
  let waiting_time = if recipe_data.waiting_time > 0 { str(recipe_data.waiting_time) + " min" } else { "" }

  recipe(
    title: recipe_data.name,
    description: recipe_data.description,
    servings: recipe_data.servings,
    servings_text: recipe_data.servings_text,
    working_time: working_time,
    waiting_time: waiting_time,
    ingredients: all_ingredients,
    steps: recipe_data.steps,
    image_path: image_path,
    page_number: page_number,
  )
}
