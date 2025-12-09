#!/usr/bin/env python3
"""
Create a curated history database with key historical events.
Since API downloads are unreliable, we'll create a manually curated dataset.
"""

import json
from pathlib import Path

OUTPUT_FILE = Path("app/data/history.json")

# Curated historical events - key events for each month/day
# This is a starter set that can be expanded
history_data = {
    "1": {  # January
        "1": [
            "1863: Emancipation Proclamation issued by Abraham Lincoln.",
            "1959: Fidel Castro's forces take over Cuba.",
            "2002: Euro currency introduced in 12 European countries."
        ],
        "15": [
            "1929: Martin Luther King Jr. born.",
            "2001: Wikipedia launched."
        ],
        "20": [
            "1981: Iran releases 52 American hostages after 444 days.",
            "2009: Barack Obama inaugurated as 44th US President."
        ],
    },
    "2": {  # February
        "4": [
            "1945: Yalta Conference begins.",
            "2004: Facebook launched by Mark Zuckerberg."
        ],
        "11": [
            "1990: Nelson Mandela released from prison after 27 years.",
            "2011: Egyptian President Hosni Mubarak resigns."
        ],
        "14": [
            "1929: St. Valentine's Day Massacre in Chicago.",
            "1989: Salman Rushdie's 'The Satanic Verses' published."
        ],
    },
    "3": {  # March
        "15": [
            "44 BC: Julius Caesar assassinated.",
            "1965: President Johnson calls for equal voting rights."
        ],
        "20": [
            "2003: US-led coalition invades Iraq.",
            "2015: Total solar eclipse visible in Europe."
        ],
    },
    "4": {  # April
        "12": [
            "1861: American Civil War begins with attack on Fort Sumter.",
            "1961: Yuri Gagarin becomes first human in space.",
            "1981: First Space Shuttle (Columbia) launched."
        ],
        "15": [
            "1912: RMS Titanic sinks in the North Atlantic.",
            "1947: Jackie Robinson breaks baseball's color barrier."
        ],
        "22": [
            "1970: First Earth Day celebrated.",
            "1994: Richard Nixon dies."
        ],
    },
    "5": {  # May
        "4": [
            "1970: Kent State shootings occur during Vietnam War protests.",
            "1979: Margaret Thatcher becomes UK Prime Minister."
        ],
        "8": [
            "1945: V-E Day - Germany surrenders, ending WWII in Europe.",
            "1980: World Health Organization declares smallpox eradicated."
        ],
    },
    "6": {  # June
        "6": [
            "1944: D-Day - Allied forces invade Normandy.",
            "1968: Robert F. Kennedy assassinated."
        ],
        "20": [
            "1837: Queen Victoria ascends to British throne.",
            "1963: US and USSR establish 'hotline' for crisis communication."
        ],
    },
    "7": {  # July
        "4": [
            "1776: United States Declaration of Independence signed.",
            "1863: Battle of Gettysburg ends."
        ],
        "20": [
            "1969: Apollo 11 lands on the Moon - 'One small step for man...'",
            "1976: Viking 1 lands on Mars."
        ],
    },
    "8": {  # August
        "6": [
            "1945: Atomic bomb dropped on Hiroshima.",
            "1965: Voting Rights Act signed into law."
        ],
        "15": [
            "1945: Japan surrenders, ending WWII.",
            "1969: Woodstock music festival begins."
        ],
    },
    "9": {  # September
        "11": [
            "2001: 9/11 terrorist attacks on World Trade Center and Pentagon.",
            "1973: Chilean President Salvador Allende overthrown in coup."
        ],
        "17": [
            "1787: US Constitution signed in Philadelphia.",
            "1862: Battle of Antietam - bloodiest single day in US history."
        ],
    },
    "10": {  # October
        "12": [
            "1492: Christopher Columbus reaches the Americas.",
            "2000: USS Cole bombing in Yemen."
        ],
        "29": [
            "1929: Black Tuesday - Stock market crash begins Great Depression.",
            "1969: First message sent over ARPANET (precursor to Internet)."
        ],
    },
    "11": {  # November
        "9": [
            "1989: Berlin Wall falls.",
            "1965: Great Northeast Blackout affects 30 million people."
        ],
        "22": [
            "1963: President John F. Kennedy assassinated in Dallas.",
            "1995: Toy Story released - first fully computer-animated feature film."
        ],
    },
    "12": {  # December
        "7": [
            "1941: Pearl Harbor attacked by Japan, US enters WWII.",
            "1972: Apollo 17 launches - last manned Moon mission."
        ],
        "8": [
            "1980: John Lennon assassinated in New York.",
            "1991: Soviet Union officially dissolved."
        ],
        "25": [
            "0: Traditional date of Jesus Christ's birth.",
            "1991: Mikhail Gorbachev resigns as Soviet President."
        ],
    },
}

# Save to file
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(history_data, f, indent=2, ensure_ascii=False)

print(f"Created history database with {sum(len(day_events) for month_data in history_data.values() for day_events in month_data.values())} events")
print(f"Saved to {OUTPUT_FILE}")

