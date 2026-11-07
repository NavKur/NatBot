// Plain-English descriptions of the 2D profile matrix (Capacity x Tendency).

export const CAPACITY_TEXT: Record<string, string> = {
  'The Over-Leveraged': 'Debts are taking a big bite each month, so there is little room for surprises.',
  'The Scrapper': 'You cover the essentials, but there is not much of a cushion if something goes wrong.',
  'The Stabilizer': 'You have a steady base and some buffer. Now it is about growing the gap.',
  'The Accumulator': 'You have built a healthy cushion. The next step is putting it to work with intent.',
}

export const TENDENCY_TEXT: Record<string, string> = {
  'The Comfort-Buyer': 'When you are tired or stressed, spending is how you look after yourself, like takeaways or late-night baskets.',
  'The Status-Seeker': 'Keeping up with people around you shapes what you buy, from clothes to meals out.',
  'The Experience-Junkie': 'You spend on moments: nights out, gigs and trips. Great memories, fast-moving money.',
  'The Panic-Hoarder': 'Worry about money makes you hold on tight, sometimes in ways that cost you.',
}

export function shortName(archetype: string): string {
  return archetype.replace(/^The /, '')
}
