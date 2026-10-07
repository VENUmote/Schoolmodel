const STATIC_DEMO = window.SAGE_STATIC_DEMO === true;

const menuToggle = document.querySelector(".menu-toggle");
const siteNav = document.querySelector("#site-nav");

menuToggle.addEventListener("click", () => {
  const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "Open menu" : "Close menu");
  siteNav.classList.toggle("is-open", !isOpen);
});

const installAppButton = document.querySelector("#install-app");
const connectivityStatus = document.querySelector("#connectivity-status");
let pendingInstallPrompt = null;

function updateConnectivityStatus() {
  connectivityStatus.textContent = navigator.onLine ? "Online · app ready" : "Offline · saved pages";
}

function noteServerUnavailable(error) {
  if (error instanceof TypeError) {
    connectivityStatus.textContent = navigator.onLine
      ? "Server unavailable · app ready"
      : "Offline · saved pages";
  }
}

window.addEventListener("online", updateConnectivityStatus);
window.addEventListener("offline", updateConnectivityStatus);
updateConnectivityStatus();

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  pendingInstallPrompt = event;
  installAppButton.textContent = "Install app";
  connectivityStatus.textContent = "Ready to install";
});

window.addEventListener("appinstalled", () => {
  pendingInstallPrompt = null;
  installAppButton.hidden = true;
  connectivityStatus.textContent = "App installed";
});

installAppButton.addEventListener("click", async () => {
  if (!pendingInstallPrompt) {
    connectivityStatus.textContent = "To install, use your browser menu and choose Install app or Add to Home Screen.";
    return;
  }
  const prompt = pendingInstallPrompt;
  pendingInstallPrompt = null;
  try {
    await prompt.prompt();
    const choice = await prompt.userChoice;
    connectivityStatus.textContent = choice.outcome === "accepted"
      ? "App installed"
      : "Install dismissed. You can try again from this button.";
  } catch (error) {
    connectivityStatus.textContent = "App installation could not be opened. Use your browser menu instead.";
    console.error("Could not open the school app installation prompt:", error);
  }
});

if (window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone) {
  installAppButton.hidden = true;
  connectivityStatus.textContent = "App installed";
}

if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/service-worker.js")
    .then(() => {
      if (navigator.onLine && connectivityStatus.textContent === "Online · app ready") {
        connectivityStatus.textContent = "Online · app ready";
      }
    })
    .catch((error) => {
      connectivityStatus.textContent = "App offline setup failed";
      console.error("Could not set up the school app for offline use:", error);
    });
}

siteNav.addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    menuToggle.setAttribute("aria-expanded", "false");
    menuToggle.setAttribute("aria-label", "Open menu");
    siteNav.classList.remove("is-open");
  }
});

const homeSlider = document.querySelector(".home-slider");
const heroSlides = [...document.querySelectorAll("[data-hero-slide]")];
const heroDots = [...document.querySelectorAll("[data-hero-index]")];
const heroAutoplayButton = document.querySelector("#hero-autoplay");
const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
let activeHeroSlide = 0;
let heroAutoplayTimer = null;
let heroAutoplayPaused = reduceMotionQuery.matches;
let heroPointerInside = false;
let heroHasFocus = false;

function stopHeroAutoplay() {
  if (heroAutoplayTimer !== null) {
    window.clearInterval(heroAutoplayTimer);
    heroAutoplayTimer = null;
  }
}

function updateHeroAutoplay() {
  stopHeroAutoplay();
  heroAutoplayButton.hidden = reduceMotionQuery.matches;
  heroAutoplayButton.setAttribute("aria-pressed", String(heroAutoplayPaused));
  heroAutoplayButton.setAttribute(
    "aria-label",
    heroAutoplayPaused ? "Resume automatic highlights" : "Pause automatic highlights",
  );
  heroAutoplayButton.textContent = heroAutoplayPaused ? "▶" : "Ⅱ";
  if (
    reduceMotionQuery.matches
    || heroAutoplayPaused
    || heroPointerInside
    || heroHasFocus
    || document.hidden
  ) {
    return;
  }
  heroAutoplayTimer = window.setInterval(() => {
    showHeroSlide((activeHeroSlide + 1) % heroSlides.length);
  }, 7000);
}

function showHeroSlide(index) {
  if (!Number.isInteger(index) || index < 0 || index >= heroSlides.length) {
    throw new RangeError("The selected school highlight is unavailable.");
  }
  activeHeroSlide = index;
  heroSlides.forEach((slide, slideIndex) => {
    const isActive = slideIndex === activeHeroSlide;
    slide.hidden = !isActive;
    slide.setAttribute("aria-hidden", String(!isActive));
    slide.classList.toggle("is-active", isActive);
  });
  heroDots.forEach((dot, dotIndex) => {
    dot.setAttribute("aria-pressed", String(dotIndex === activeHeroSlide));
  });
  updateHeroAutoplay();
}

document.querySelector("#hero-previous").addEventListener("click", () => {
  showHeroSlide((activeHeroSlide + heroSlides.length - 1) % heroSlides.length);
});
document.querySelector("#hero-next").addEventListener("click", () => {
  showHeroSlide((activeHeroSlide + 1) % heroSlides.length);
});
heroDots.forEach((dot) => {
  dot.addEventListener("click", () => {
    showHeroSlide(Number(dot.dataset.heroIndex));
  });
});
heroAutoplayButton.addEventListener("click", () => {
  heroAutoplayPaused = !heroAutoplayPaused;
  updateHeroAutoplay();
});
homeSlider.addEventListener("pointerenter", () => {
  heroPointerInside = true;
  updateHeroAutoplay();
});
homeSlider.addEventListener("pointerleave", () => {
  heroPointerInside = false;
  updateHeroAutoplay();
});
homeSlider.addEventListener("focusin", () => {
  heroHasFocus = true;
  updateHeroAutoplay();
});
homeSlider.addEventListener("focusout", (event) => {
  heroHasFocus = homeSlider.contains(event.relatedTarget);
  updateHeroAutoplay();
});
document.addEventListener("visibilitychange", updateHeroAutoplay);
reduceMotionQuery.addEventListener("change", () => {
  if (reduceMotionQuery.matches) {
    heroAutoplayPaused = true;
  }
  updateHeroAutoplay();
});
showHeroSlide(0);

const themes = [
  { id: "sage", label: "Sage" },
  { id: "ocean", label: "Ocean" },
  { id: "sunset", label: "Sunset" },
  { id: "berry", label: "Berry" },
];
const themeToggle = document.querySelector("#theme-toggle");
const themeToggleLabel = document.querySelector("#theme-toggle-label");
const themeOptions = document.querySelector("#theme-options");

function closeThemeOptions() {
  themeOptions.hidden = true;
  themeToggle.setAttribute("aria-expanded", "false");
}

function setTheme(themeId, savePreference = false) {
  const theme = themes.find((option) => option.id === themeId) || themes[0];
  document.documentElement.dataset.theme = theme.id;
  themeToggleLabel.textContent = `${theme.label} colors`;
  themeToggle.setAttribute("aria-label", `Color theme: ${theme.label}. Open to choose a theme.`);
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme.id));
  });
  document.querySelector('meta[name="theme-color"]').content = theme.id === "sage"
    ? "#f8f7f2"
    : getComputedStyle(document.documentElement).getPropertyValue("--theme-panel").trim();

  if (savePreference) {
    try {
      window.localStorage.setItem("sage-school-theme", theme.id);
    } catch (error) {
      if (!["SecurityError", "QuotaExceededError"].includes(error.name)) {
        throw error;
      }
    }
  }
}

try {
  const savedTheme = window.localStorage.getItem("sage-school-theme");
  setTheme(themes.some((theme) => theme.id === savedTheme) ? savedTheme : "sage");
} catch (error) {
  if (error.name !== "SecurityError") {
    throw error;
  }
  setTheme("sage");
}

themeToggle.addEventListener("click", () => {
  const isExpanded = themeToggle.getAttribute("aria-expanded") === "true";
  themeOptions.hidden = isExpanded;
  themeToggle.setAttribute("aria-expanded", String(!isExpanded));
});

document.querySelectorAll("[data-theme-choice]").forEach((button) => {
  button.addEventListener("click", () => {
    setTheme(button.dataset.themeChoice, true);
  });
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".theme-picker")) {
    closeThemeOptions();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !themeOptions.hidden) {
    closeThemeOptions();
    themeToggle.focus();
  }
});

const revealItems = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

const gradeSyllabi = {
  nursery: {
    label: "Nursery",
    stage: "Foundational stage · play-based learning",
    note: "A gentle start through stories, play, talk, movement, and hands-on discovery. There is no single prescribed CBSE Nursery textbook syllabus.",
    subjects: [
      { name: "Language & stories", topics: "Listening, speaking, picture books, rhymes, new words, and telling simple stories." },
      { name: "Early maths", topics: "Sorting, matching, shapes, patterns, counting objects, and everyday comparisons." },
      { name: "My world", topics: "Self, family, friends, familiar places, nature, and caring routines." },
      { name: "Creative play", topics: "Drawing, music, pretend play, movement, coordination, and sharing." },
    ],
  },
  lkg: {
    label: "LKG",
    stage: "Foundational stage · play-based learning",
    note: "Learning grows through conversation, stories, guided play, and activities children can see and touch—not rote exam preparation.",
    subjects: [
      { name: "Language & stories", topics: "Sound awareness, vocabulary, picture reading, conversation, rhymes, and early mark-making." },
      { name: "Early maths", topics: "Counting sets, number sense, sorting, shape, position, comparison, and repeating patterns." },
      { name: "My world", topics: "Family and community, plants and animals, weather, healthy habits, and safety." },
      { name: "Creative play", topics: "Art, songs, movement, imagination, fine-motor play, and learning to work together." },
    ],
  },
  ukg: {
    label: "UKG",
    stage: "Foundational stage · ready for Class 1",
    note: "A gradual bridge to primary school builds confidence, understanding, and early literacy and numeracy through meaningful activity.",
    subjects: [
      { name: "Language & stories", topics: "Listening and speaking, phonological awareness, early reading, familiar words, and shared writing." },
      { name: "Early maths", topics: "Number sense, counting and grouping, simple operations with objects, patterns, shapes, and measurement." },
      { name: "My world", topics: "People and places, the natural world, health, routines, responsible choices, and observation." },
      { name: "Creative play", topics: "Drawing, music, movement, dramatic play, coordination, expression, and cooperative games." },
    ],
  },
  "class-1": {
    label: "Class 1",
    stage: "Preparatory learning · early primary",
    note: "Concrete, playful activities help learners build foundational literacy and numeracy and make sense of familiar people and places.",
    subjects: [
      { name: "Languages", topics: "Listening, conversation, sound-letter links, familiar words, picture reading, and shared writing." },
      { name: "Mathematics", topics: "Numbers and counting, comparing groups, addition and subtraction ideas, shapes, patterns, and everyday measures." },
      { name: "The world around me", topics: "Myself and family, school and community, plants and animals, weather, cleanliness, and safety." },
      { name: "Arts & wellbeing", topics: "Drawing, stories, music, movement, games, cooperation, and expressing feelings." },
    ],
  },
  "class-2": {
    label: "Class 2",
    stage: "Preparatory learning · early primary",
    note: "Learners practise reading, writing, number sense, and observation with familiar examples and hands-on activities.",
    subjects: [
      { name: "Languages", topics: "Reading short texts, vocabulary, listening and speaking, sentence building, and guided writing." },
      { name: "Mathematics", topics: "Place value and number patterns, addition and subtraction, early multiplication and sharing, shapes, time, and measurement." },
      { name: "The world around me", topics: "Family and neighbourhood, plants, animals, food, water, local seasons, healthy habits, and safety." },
      { name: "Arts & wellbeing", topics: "Creative expression, rhythm, movement, games, collaboration, and self-care routines." },
    ],
  },
  "class-3": {
    label: "Class 3",
    stage: "Preparatory learning · primary",
    note: "The curriculum builds fluency and connects learning across language, mathematics, the environment, and everyday life.",
    subjects: [
      { name: "Languages", topics: "Comprehension, read-alouds, vocabulary, grammar in context, paragraph writing, and speaking." },
      { name: "Mathematics", topics: "Place value, the four operations, multiplication facts, fractions in context, measurement, shapes, and data." },
      { name: "Environmental studies", topics: "Food and health, water, homes and work, plants and animals, travel, and our neighbourhood." },
      { name: "Arts & wellbeing", topics: "Art, local stories, music, movement, games, and cooperative learning." },
    ],
  },
  "class-4": {
    label: "Class 4",
    stage: "Preparatory learning · primary",
    note: "Learners develop deeper reading, mathematical reasoning, and inquiry into their community and natural environment.",
    subjects: [
      { name: "Languages", topics: "Reading for meaning, vocabulary and grammar, short summaries, composition, and oral presentation." },
      { name: "Mathematics", topics: "Larger numbers, operations and estimation, fractions, measurement, geometry, and interpreting data." },
      { name: "Environmental studies", topics: "Living things and habitats, resources, water and food, maps and travel, occupations, and community." },
      { name: "Arts & wellbeing", topics: "Visual arts, music, physical activity, games, safety, and working in a team." },
    ],
  },
  "class-5": {
    label: "Class 5",
    stage: "Preparatory learning · primary",
    note: "A bridge to middle school strengthens subject understanding, problem-solving, reading comprehension, and independent work.",
    subjects: [
      { name: "Languages", topics: "Comprehension, vocabulary and grammar in context, organised writing, library reading, and discussion." },
      { name: "Mathematics", topics: "Operations and estimation, fractions and decimals, patterns, factors, measurement, shapes, and data." },
      { name: "Environmental studies", topics: "Ecosystems, human body and health, food and farming, water and resources, maps, and local communities." },
      { name: "Arts & wellbeing", topics: "Creative projects, music, physical education, games, digital awareness, and collaboration." },
    ],
  },
  "class-6": {
    label: "Class 6",
    stage: "Middle stage · subject learning",
    note: "A move towards disciplinary learning develops explanation, investigation, problem-solving, and independent study.",
    subjects: [
      { name: "Languages", topics: "Reading a wider range of texts, grammar and vocabulary, creative and factual writing, listening, and speaking." },
      { name: "Mathematics", topics: "Knowing numbers, whole-number operations, factors and multiples, fractions, basic geometry, and data handling." },
      { name: "Science", topics: "Materials, living organisms and their surroundings, food, motion and measurement, light, and simple investigations." },
      { name: "Social science", topics: "Maps and the Earth, early history, communities and diversity, local governance, and livelihoods." },
      { name: "Arts, skills & wellbeing", topics: "Art and physical education, practical projects, responsible digital use, and teamwork." },
    ],
  },
  "class-7": {
    label: "Class 7",
    stage: "Middle stage · subject learning",
    note: "Learners connect ideas between units, support claims with evidence, and apply subject knowledge to everyday questions.",
    subjects: [
      { name: "Languages", topics: "Literature and non-fiction, comprehension, grammar and vocabulary, structured writing, and presentation." },
      { name: "Mathematics", topics: "Integers and rational numbers, fractions and decimals, simple equations, ratios, geometry, and data." },
      { name: "Science", topics: "Nutrition and living processes, heat, motion and time, electric current, light, and the environment." },
      { name: "Social science", topics: "Medieval history themes, environment and resources, state government, democracy, and economic life." },
      { name: "Arts, skills & wellbeing", topics: "Art and physical education, making and design, digital awareness, and collaborative work." },
    ],
  },
  "class-8": {
    label: "Class 8",
    stage: "Middle stage · transition to secondary",
    note: "The focus is on deeper conceptual understanding, investigation, communication, and preparation for secondary-level subjects.",
    subjects: [
      { name: "Languages", topics: "Close reading, diverse literature and informational texts, grammar, analytical writing, and discussion." },
      { name: "Mathematics", topics: "Rational numbers, linear equations, percentages and proportional reasoning, geometry, mensuration, and data." },
      { name: "Science", topics: "Materials and change, cells and reproduction, force and pressure, sound, light, electricity, and resources." },
      { name: "Social science", topics: "Modern history themes, resources and development, the Constitution, parliament, justice, and livelihoods." },
      { name: "Arts, skills & wellbeing", topics: "Art and physical education, practical problem-solving, digital literacy, and project work." },
    ],
  },
  "class-9": {
    label: "Class 9",
    stage: "Secondary stage · CBSE subject curriculum",
    note: "The topic guide below summarises major subject areas. Use the linked CBSE syllabus and Sage High School’s current subject plan for the exact prescribed units and assessment.",
    subjects: [
      { name: "English & languages", topics: "Language and literature: reading comprehension, writing, grammar, and prescribed texts. The CBSE portal also lists language-specific courses, including Telugu Telangana." },
      { name: "Mathematics", topics: "Number systems, polynomials, coordinate geometry, linear equations, geometry, mensuration, statistics, and probability." },
      { name: "Science", topics: "Matter and atoms, cells and tissues, motion, force and gravitation, work and energy, sound, and food resources." },
      { name: "Social science", topics: "India and its physical environment; democracy and constitutional institutions; and historical themes such as revolutions and social change." },
      { name: "Assessment & options", topics: "Choose languages, electives, and internal-assessment subjects only from the school’s CBSE-approved combination. Practical work and projects form part of subject learning." },
    ],
  },
  "class-10": {
    label: "Class 10",
    stage: "Secondary stage · CBSE board preparation",
    note: "The topic guide below summarises major subject areas, not an official replacement syllabus. Check the CBSE documents for your examination year; Mathematics may have Basic and Standard course options.",
    subjects: [
      { name: "English & languages", topics: "Language and literature: reading comprehension, writing, grammar, and prescribed texts. Ask which CBSE language and course the school offers." },
      { name: "Mathematics", topics: "Real numbers, algebra, coordinate geometry, geometry, trigonometry, mensuration, statistics, and probability." },
      { name: "Science", topics: "Chemical reactions and materials, life processes and heredity, light, electricity and magnetism, and environment." },
      { name: "Social science", topics: "Nationalism and history; resources and development; power-sharing and federalism; development, money, and economic sectors." },
      { name: "Assessment & options", topics: "Check the current CBSE scheme for language and elective choices, practical or project requirements, internal assessment, and the school’s approved subject combination." },
    ],
  },
};

const syllabusContent = document.querySelector("#syllabus-content");
const gradeButtons = document.querySelectorAll(".grade-button");

function renderSyllabus(gradeId) {
  const syllabus = gradeSyllabi[gradeId];
  if (!syllabus) {
    throw new Error(`No syllabus learning guide is available for grade "${gradeId}".`);
  }

  gradeButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.grade === gradeId));
  });

  const heading = document.createElement("div");
  heading.className = "syllabus-panel-heading";

  const headingCopy = document.createElement("div");
  const stage = document.createElement("p");
  stage.className = "syllabus-stage";
  stage.textContent = syllabus.stage;
  const title = document.createElement("h3");
  title.textContent = `${syllabus.label} learning outline`;
  headingCopy.append(stage, title);

  const guideTag = document.createElement("span");
  guideTag.className = "syllabus-guide-tag";
  guideTag.textContent = gradeId === "class-9" || gradeId === "class-10"
    ? "CBSE SECONDARY"
    : "NCERT / NCF GUIDE";
  heading.append(headingCopy, guideTag);

  const note = document.createElement("p");
  note.className = "syllabus-grade-note";
  note.textContent = syllabus.note;

  const subjects = document.createElement("div");
  subjects.className = "syllabus-subject-grid";
  syllabus.subjects.forEach((subject, index) => {
    const card = document.createElement("article");
    card.className = "syllabus-subject";
    const number = document.createElement("span");
    number.className = "syllabus-subject-number";
    number.textContent = String(index + 1).padStart(2, "0");
    const name = document.createElement("h4");
    name.textContent = subject.name;
    const topics = document.createElement("p");
    topics.textContent = subject.topics;
    card.append(number, name, topics);
    subjects.append(card);
  });

  syllabusContent.replaceChildren(heading, note, subjects);
}

gradeButtons.forEach((button) => {
  button.addEventListener("click", () => renderSyllabus(button.dataset.grade));
});
renderSyllabus("class-10");

const greenActionInputs = [...document.querySelectorAll("[data-green-action]")];
const greenProgressCount = document.querySelector("#green-progress-count");
const greenProgressMessage = document.querySelector("#green-progress-message");
const greenProgressBar = document.querySelector("#green-progress-bar");
const greenProgressFill = document.querySelector("#green-progress-fill");
const greenStorageNote = document.querySelector("#green-storage-note");
const clearGreenActions = document.querySelector("#clear-green-actions");
let greenStorageAvailable = true;
let greenActionDate = getLocalCalendarDate();
let greenStorageWarning = "";

function getLocalCalendarDate() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function greenActionStorageKey() {
  return "sage-green-actions";
}

function loadGreenActions() {
  let selectedActions = [];
  try {
    const savedActions = window.localStorage.getItem(greenActionStorageKey());
    if (savedActions !== null) {
      const savedState = JSON.parse(savedActions);
      if (
        savedState
        && typeof savedState === "object"
        && savedState.date === greenActionDate
        && Array.isArray(savedState.actions)
      ) {
        selectedActions = savedState.actions.filter((action) =>
          greenActionInputs.some((input) => input.dataset.greenAction === action)
        );
      }
    }
  } catch (error) {
    if (error.name === "SyntaxError") {
      greenStorageWarning = "A damaged check-in was cleared. You can start fresh.";
    } else if (error.name !== "SecurityError" && error.name !== "QuotaExceededError") {
      throw error;
    } else {
      greenStorageAvailable = false;
    }
  }
  greenActionInputs.forEach((input) => {
    input.checked = selectedActions.includes(input.dataset.greenAction);
  });
  updateGreenActions();
}

function updateGreenActions() {
  const selectedActions = greenActionInputs
    .filter((input) => input.checked)
    .map((input) => input.dataset.greenAction);
  const progress = selectedActions.length;
  greenProgressCount.textContent = `${progress} of ${greenActionInputs.length} actions`;
  greenProgressMessage.textContent = progress === greenActionInputs.length
    ? "Wonderful care for our shared home."
    : progress > 0
      ? "Every little action counts."
      : "Choose an action you completed today.";
  greenProgressBar.setAttribute("aria-valuenow", String(progress));
  greenProgressFill.style.width = `${(progress / greenActionInputs.length) * 100}%`;
  greenStorageNote.textContent = !greenStorageAvailable
    ? "Browser storage is unavailable. Check-ins will last only while this page is open."
    : greenStorageWarning || "Check-ins are saved only on this device and reset each day.";
  if (greenStorageAvailable) {
    try {
      window.localStorage.setItem(
        greenActionStorageKey(),
        JSON.stringify({ date: greenActionDate, actions: selectedActions }),
      );
    } catch (error) {
      if (error.name !== "SecurityError" && error.name !== "QuotaExceededError") {
        throw error;
      }
      greenStorageAvailable = false;
      greenStorageNote.textContent = "Browser storage is unavailable. Check-ins will last only while this page is open.";
    }
  }
}

function resetGreenActionsForNewDay() {
  const currentDate = getLocalCalendarDate();
  if (currentDate === greenActionDate) {
    return;
  }
  greenActionDate = currentDate;
  greenActionInputs.forEach((input) => {
    input.checked = false;
  });
  updateGreenActions();
}

greenActionInputs.forEach((input) => {
  input.addEventListener("change", () => {
    const isChecked = input.checked;
    resetGreenActionsForNewDay();
    input.checked = isChecked;
    updateGreenActions();
  });
});
clearGreenActions.addEventListener("click", () => {
  greenActionInputs.forEach((input) => {
    input.checked = false;
  });
  updateGreenActions();
});
document.addEventListener("visibilitychange", resetGreenActionsForNewDay);
loadGreenActions();

const achievementFilters = document.querySelectorAll(".achievement-filter");
const achievementGrid = document.querySelector("#achievement-grid");
const achievementResultsCount = document.querySelector("#achievement-results-count");
const achievementSportNames = {
  cricket: "Cricket",
  football: "Football",
  volleyball: "Volleyball",
  tennis: "Tennis",
  badminton: "Badminton",
  chess: "Chess",
  carrom: "Carrom",
  scrabble: "Scrabble",
  "table-tennis": "Table tennis",
};
const achievementCardColors = ["peach", "lilac", "mint", "yellow"];
let schoolAchievements = [];
let selectedAchievementSport = "all";

function renderAchievements() {
  const achievements = schoolAchievements.filter((achievement) =>
    selectedAchievementSport === "all" || achievement.sport === selectedAchievementSport
  );
  achievementGrid.replaceChildren(...achievements.map((achievement, index) => {
    const card = document.createElement("article");
    card.className = "achievement-card";
    const ribbon = document.createElement("div");
    ribbon.className = `achievement-ribbon achievement-ribbon-${achievementCardColors[index % achievementCardColors.length]}`;
    ribbon.textContent = ["✦", "↗", "✳", "⌁"][index % 4];
    const sport = document.createElement("p");
    sport.className = "achievement-sport-label";
    sport.textContent = `${achievementSportNames[achievement.sport] || achievement.sport} · SCHOOL ACTIVITY`;
    const title = document.createElement("h4");
    title.textContent = achievement.title;
    const className = document.createElement("p");
    className.className = "achievement-student";
    className.textContent = achievement.className;
    const award = document.createElement("span");
    award.className = "achievement-award";
    award.textContent = achievement.isSample && !achievement.award.startsWith("SAMPLE ·")
      ? `SAMPLE · ${achievement.award}`
      : achievement.award;
    card.append(ribbon, sport, title, className, award);
    return card;
  }));
  achievementResultsCount.textContent = schoolAchievements.length
    ? `Showing ${achievements.length} ${selectedAchievementSport === "all" ? "school" : achievementSportNames[selectedAchievementSport].toLowerCase()} highlight${achievements.length === 1 ? "" : "s"}`
    : "No activity highlights have been added yet.";
}

achievementFilters.forEach((filter) => {
  filter.addEventListener("click", () => {
    selectedAchievementSport = filter.dataset.sport;
    achievementFilters.forEach((button) => {
      button.setAttribute("aria-pressed", String(button === filter));
    });
    renderAchievements();
  });
});

async function loadAchievements() {
  if (STATIC_DEMO) {
    return;
  }
  const response = await fetch("/api/achievements");
  const data = await response.json();
  if (!response.ok || !Array.isArray(data.achievements)) {
    throw new Error(data.error || `Activity highlights request failed (${response.status}).`);
  }
  schoolAchievements = data.achievements;
  renderAchievements();
}

loadAchievements().catch((error) => {
  noteServerUnavailable(error);
  achievementResultsCount.textContent = "Activity highlights could not be loaded. Please refresh or contact the school.";
  console.error("Could not load school activity highlights:", error);
});

const schoolUpdatesList = document.querySelector("#school-updates-list");
let schoolUpdates = [];

function schoolUpdateDateLabel(value) {
  if (!value) {
    return "School notice";
  }
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function renderSchoolUpdates() {
  if (!schoolUpdates.length) {
    schoolUpdatesList.textContent = "No notices or upcoming events have been posted yet. Please check with the school office for current dates.";
    schoolUpdatesList.className = "school-updates-list";
    const emptyMessage = document.createElement("p");
    emptyMessage.className = "school-updates-empty";
    emptyMessage.textContent = schoolUpdatesList.textContent;
    schoolUpdatesList.replaceChildren(emptyMessage);
    return;
  }

  schoolUpdatesList.className = "school-updates-list";
  schoolUpdatesList.replaceChildren(...schoolUpdates.map((update) => {
    const card = document.createElement("article");
    card.className = "school-update-card";
    const meta = document.createElement("p");
    meta.className = "school-update-meta";
    meta.textContent = update.type === "event"
      ? `Upcoming event · ${schoolUpdateDateLabel(update.date)}`
      : "School notice";
    const title = document.createElement("h3");
    title.textContent = update.title;
    const details = document.createElement("p");
    details.textContent = update.details;
    card.append(meta, title, details);
    return card;
  }));
}

async function loadSchoolUpdates() {
  if (STATIC_DEMO) {
    schoolUpdates = [];
    renderSchoolUpdates();
    schoolUpdatesList.firstElementChild.textContent = "Live notices and event dates are published by authorised staff on the school website. Contact the school office for current information.";
    return;
  }
  const response = await fetch("/api/school-updates");
  const data = await response.json();
  if (!response.ok || !Array.isArray(data.updates)) {
    throw new Error(data.error || `School updates request failed (${response.status}).`);
  }
  schoolUpdates = data.updates;
  renderSchoolUpdates();
}

loadSchoolUpdates().catch((error) => {
  noteServerUnavailable(error);
  schoolUpdatesList.textContent = "School notices could not be loaded. Please contact the school office for current information.";
  console.error("Could not load school notices and events:", error);
});

function refreshStaffSchoolUpdates() {
  const list = document.querySelector("#staff-school-updates-list");
  if (!schoolUpdates.length) {
    list.textContent = "No current notices or upcoming events to manage.";
    return;
  }
  list.replaceChildren(...schoolUpdates.map((update) => {
    const item = document.createElement("div");
    item.className = "staff-school-update-item";
    const text = document.createElement("span");
    text.textContent = `${update.type === "event" ? `${schoolUpdateDateLabel(update.date)} · Event` : "Notice"} · ${update.title}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "staff-logout";
    remove.dataset.deleteSchoolUpdate = String(update.updateId);
    remove.textContent = "Remove";
    item.append(text, remove);
    return item;
  }));
}

const schoolUpdateForm = document.querySelector("#school-update-form");
const schoolUpdateType = document.querySelector("#school-update-type");
const schoolUpdateDate = document.querySelector("#school-update-date");
const minimumEventDate = new Date();
schoolUpdateDate.min = [
  minimumEventDate.getFullYear(),
  String(minimumEventDate.getMonth() + 1).padStart(2, "0"),
  String(minimumEventDate.getDate()).padStart(2, "0"),
].join("-");
schoolUpdateType.addEventListener("change", () => {
  const isEvent = schoolUpdateType.value === "event";
  schoolUpdateDate.disabled = !isEvent;
  schoolUpdateDate.required = isEvent;
  if (!isEvent) {
    schoolUpdateDate.value = "";
  }
});

schoolUpdateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = new FormData(schoolUpdateForm);
  try {
    await staffRequest("/api/staff/school-updates", {
      method: "POST",
      body: JSON.stringify({
        type: values.get("type"),
        title: values.get("title"),
        date: values.get("date") || null,
        details: values.get("details"),
      }),
    });
    schoolUpdateForm.reset();
    schoolUpdateType.dispatchEvent(new Event("change"));
    await loadSchoolUpdates();
    refreshStaffSchoolUpdates();
    showStaffMessage("The school update is now published.");
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

document.querySelector("#staff-school-updates-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-school-update]");
  if (!button) {
    return;
  }
  try {
    await staffRequest("/api/staff/school-updates", {
      method: "DELETE",
      body: JSON.stringify({ updateId: Number(button.dataset.deleteSchoolUpdate) }),
    });
    await loadSchoolUpdates();
    refreshStaffSchoolUpdates();
    showStaffMessage("The school update has been removed.");
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

const busAnnualFee = document.querySelector("#bus-annual-fee");
const busMonthlyFee = document.querySelector("#bus-monthly-fee");
const busDistanceLabel = document.querySelector("#bus-distance-label");
const rupeeFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
let schoolFeeSchedule = [];

function renderStaffFees() {
  const staffFeeList = document.querySelector("#staff-fee-list");
  staffFeeList.replaceChildren(...schoolFeeSchedule.map((fee) => {
    const form = document.createElement("form");
    form.className = "staff-fee-form";
    form.dataset.feeId = fee.feeId;
    const heading = document.createElement("strong");
    heading.textContent = `${fee.name} · ${fee.band}`;
    const amountLabel = document.createElement("label");
    amountLabel.textContent = "Annual fee (₹)";
    const amount = document.createElement("input");
    amount.type = "number";
    amount.name = "amount";
    amount.min = "0";
    amount.max = "10000000";
    amount.step = "1";
    amount.value = String(fee.amount);
    amount.required = true;
    amountLabel.append(amount);
    const confirmationLabel = document.createElement("label");
    confirmationLabel.className = "fee-confirmation";
    const confirmation = document.createElement("input");
    confirmation.type = "checkbox";
    confirmation.name = "isConfirmed";
    confirmation.checked = fee.isConfirmed;
    confirmationLabel.append(confirmation, document.createTextNode(" Approved by the school"));
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "button button-primary";
    save.textContent = "Save";
    form.append(heading, amountLabel, confirmationLabel, save);
    return form;
  }));
}

async function loadFeeSchedule() {
  if (STATIC_DEMO) {
    return;
  }
  const response = await fetch("/api/fees");
  const data = await response.json();
  if (!response.ok || !Array.isArray(data.fees)) {
    throw new Error(data.error || `Fee schedule request failed (${response.status}).`);
  }
  schoolFeeSchedule = data.fees;
  const tuitionRows = schoolFeeSchedule.filter((fee) => fee.category === "tuition");
  const feeTable = document.querySelector("#public-fee-rows");
  feeTable.replaceChildren(...tuitionRows.map((fee, index) => {
    const row = document.createElement("tr");
    const group = document.createElement("th");
    group.scope = "row";
    const dot = document.createElement("span");
    dot.className = `fee-dot fee-dot-${achievementCardColors[index % achievementCardColors.length]}`;
    const name = document.createTextNode(fee.name);
    const band = document.createElement("small");
    band.textContent = fee.band;
    group.append(dot, name, band);
    const amountCell = document.createElement("td");
    amountCell.textContent = rupeeFormatter.format(fee.amount);
    const includes = document.createElement("td");
    includes.textContent = fee.description;
    const note = document.createElement("td");
    note.textContent = fee.isConfirmed ? "School confirmed" : "Example · verify";
    row.append(group, amountCell, includes, note);
    return row;
  }));
  const transportFees = schoolFeeSchedule.filter((fee) => fee.category === "transport");
  document.querySelectorAll(".bus-zone").forEach((button) => {
    const fee = transportFees.find((item) => item.feeId === button.dataset.feeId);
    if (fee) {
      button.dataset.annualFee = String(fee.amount);
      button.setAttribute("aria-label", `${fee.band} sample bus fare, ${rupeeFormatter.format(fee.amount)} per year`);
    }
  });
  const activeZone = document.querySelector(".bus-zone[aria-pressed='true']");
  if (activeZone) {
    activeZone.click();
  }
  const note = document.querySelector("#public-fee-note");
  note.textContent = data.allConfirmed
    ? "The school has marked these amounts confirmed. Bus transport is optional and priced separately."
    : "Example amounts from the school database; unconfirmed fees are estimates only. Please confirm current fees with the school office.";
  renderStaffFees();
}

loadFeeSchedule().catch((error) => {
  noteServerUnavailable(error);
  document.querySelector("#public-fee-rows").textContent = "The saved fee schedule could not be loaded. Please contact the school.";
  document.querySelector("#staff-fee-list").textContent = "Fees could not be loaded. Please refresh or contact the school.";
  document.querySelector("#public-fee-note").textContent = "Bus amounts shown are examples until the school fee schedule can be loaded.";
  console.error("Could not load the school fee schedule:", error);
});

document.querySelectorAll(".bus-zone").forEach((button) => {
  button.addEventListener("click", () => {
    const annualFee = Number(button.dataset.annualFee);
    const distance = button.dataset.distance;
    if (!Number.isFinite(annualFee) || annualFee < 0 || !distance) {
      throw new Error("The selected example bus fare is invalid.");
    }

    document.querySelectorAll(".bus-zone").forEach((zone) => {
      zone.setAttribute("aria-pressed", String(zone === button));
    });
    busDistanceLabel.textContent = `SAMPLE FARE · ${distance.toUpperCase()}`;
    busAnnualFee.textContent = rupeeFormatter.format(annualFee);
    busMonthlyFee.textContent = rupeeFormatter.format(annualFee / 10);
  });
});

const busGpsStart = document.querySelector("#bus-gps-start");
const busGpsStop = document.querySelector("#bus-gps-stop");
const busDriverStatus = document.querySelector("#bus-driver-status");
let busGpsWatchId = null;
let busGpsTrackingActive = false;
let busGpsUpdateQueue = Promise.resolve();

function stopBusGpsWatch() {
  busGpsTrackingActive = false;
  if (busGpsWatchId !== null && "geolocation" in navigator) {
    navigator.geolocation.clearWatch(busGpsWatchId);
  }
  busGpsWatchId = null;
  busGpsStart.hidden = false;
  busGpsStop.hidden = true;
}

function updateDriverGps(position) {
  busGpsUpdateQueue = busGpsUpdateQueue.then(async () => {
    if (!busGpsTrackingActive) {
      return;
    }
    try {
      await staffRequest("/api/staff/bus-location", {
        method: "POST",
        body: JSON.stringify({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        }),
      });
      if (!busGpsTrackingActive) {
        return;
      }
      busDriverStatus.classList.remove("is-error");
      const accuracy = Math.round(position.coords.accuracy);
      busDriverStatus.textContent = `Bus GPS is sharing. Location accuracy: about ${accuracy} m.`;
    } catch (error) {
      busDriverStatus.textContent = error.message;
      busDriverStatus.classList.add("is-error");
    }
  });
}

function reportDriverGpsError(error) {
  const messages = {
    1: "Location access was denied. Allow GPS permission to share the bus position.",
    2: "The phone can’t find its GPS position yet. Try again outdoors.",
    3: "The phone GPS timed out. Keep location enabled and try again.",
  };
  busDriverStatus.textContent = messages[error.code] || "Couldn’t read the phone’s GPS position.";
  busDriverStatus.classList.add("is-error");
}

busGpsStart.addEventListener("click", () => {
  if (!window.isSecureContext) {
    busDriverStatus.textContent = "Phone GPS requires a secure HTTPS website. Use localhost only for development.";
    busDriverStatus.classList.add("is-error");
    return;
  }
  if (!("geolocation" in navigator)) {
    busDriverStatus.textContent = "This browser does not support phone GPS sharing.";
    busDriverStatus.classList.add("is-error");
    return;
  }

  busDriverStatus.classList.remove("is-error");
  busDriverStatus.textContent = "Requesting phone GPS permission…";
  busGpsTrackingActive = true;
  busGpsWatchId = navigator.geolocation.watchPosition(
    updateDriverGps,
    reportDriverGpsError,
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 },
  );
  busGpsStart.hidden = true;
  busGpsStop.hidden = false;
});

busGpsStop.addEventListener("click", async () => {
  stopBusGpsWatch();
  busDriverStatus.classList.remove("is-error");
  try {
    await busGpsUpdateQueue;
    await staffRequest("/api/staff/bus-location/stop", { method: "POST" });
    busDriverStatus.textContent = "Trip ended. Shared bus location has been cleared.";
  } catch (error) {
    busDriverStatus.textContent = error.message;
    busDriverStatus.classList.add("is-error");
  }
});

const busParentLoginForm = document.querySelector("#bus-parent-login-form");
const busParentView = document.querySelector("#bus-parent-view");
const busParentConfigNotice = document.querySelector("#bus-parent-config-notice");
const busParentMessage = document.querySelector("#bus-parent-message");
const parentBusHeading = document.querySelector("#parent-bus-state-heading");
const parentBusUpdatedAt = document.querySelector("#parent-bus-updated-at");
const busLocationMessage = document.querySelector("#bus-location-message");
const busLocationCoordinates = document.querySelector("#bus-location-coordinates");
const busLiveIndicator = document.querySelector("#bus-live-indicator");
const busOpenLiveMap = document.querySelector("#bus-open-live-map");
let busLocationPollId = null;

function networkFailureMessage(error) {
  noteServerUnavailable(error);
  return error instanceof TypeError
    ? "The school server could not be reached. Reconnect to use this feature; saved app pages remain available offline."
    : error.message || "The school request could not be completed.";
}

async function parentBusRequest(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    throw new Error(networkFailureMessage(error));
  }
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "The parent bus request could not be completed.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function showParentBusMessage(message, isError = false) {
  busParentMessage.hidden = !message;
  busParentMessage.textContent = message;
  busParentMessage.classList.toggle("is-error", isError);
}

function clearBusLocationPoll() {
  if (busLocationPollId !== null) {
    window.clearInterval(busLocationPollId);
    busLocationPollId = null;
  }
}

function clearBusLocationDisplay(heading, message) {
  parentBusHeading.textContent = heading;
  parentBusUpdatedAt.textContent = message;
  busLocationMessage.textContent = message;
  busLocationCoordinates.textContent = "";
  busLocationCoordinates.hidden = true;
  busOpenLiveMap.removeAttribute("href");
  busOpenLiveMap.hidden = true;
  busLiveIndicator.classList.remove("is-live");
}

async function refreshParentBusLocation() {
  const location = await parentBusRequest("/api/bus/location");
  if (!location.active) {
    clearBusLocationDisplay(
      "Waiting for the driver",
      "The driver has not started GPS sharing, or the last position expired.",
    );
    return;
  }

  const latitude = Number(location.latitude);
  const longitude = Number(location.longitude);
  if (
    !Number.isFinite(latitude) || !Number.isFinite(longitude)
    || latitude < -90 || latitude > 90
    || longitude < -180 || longitude > 180
    || !Number.isFinite(location.accuracy) || location.accuracy < 0
  ) {
    throw new Error("The live bus GPS coordinates are invalid.");
  }

  const updatedAt = new Date(location.updatedAt);
  if (Number.isNaN(updatedAt.getTime())) {
    throw new Error("The live bus GPS update has an invalid time.");
  }
  parentBusHeading.textContent = "Bus 01 is sharing its live location";
  parentBusUpdatedAt.textContent = `Last updated ${updatedAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · Approx. ${Math.round(location.accuracy)} m accuracy`;
  busLocationMessage.textContent = "The shared bus location is live.";
  busLocationCoordinates.textContent = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
  busLocationCoordinates.hidden = false;
  busOpenLiveMap.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${latitude},${longitude}`)}`;
  busOpenLiveMap.hidden = false;
  busLiveIndicator.classList.add("is-live");
}

async function refreshParentBusSession() {
  if (STATIC_DEMO) {
    return;
  }
  const session = await parentBusRequest("/api/bus/parent/session");
  busParentConfigNotice.hidden = session.enabled;
  busParentLoginForm.hidden = !session.enabled || session.authenticated;
  busParentView.hidden = !session.authenticated;
  if (!session.authenticated) {
    clearBusLocationPoll();
    clearBusLocationDisplay(
      "Sign in to view the bus",
      "Bus location is only available to signed-in parents and guardians.",
    );
    return;
  }

  await refreshParentBusLocation();
  if (busLocationPollId === null) {
    busLocationPollId = window.setInterval(() => {
      refreshParentBusLocation().catch((error) => {
        if (error.status === 401) {
          refreshParentBusSession().catch((sessionError) => {
            showParentBusMessage(sessionError.message, true);
          });
          return;
        }
        clearBusLocationDisplay(
          "Bus location unavailable",
          "The live bus location could not be refreshed. Please try again shortly.",
        );
        showParentBusMessage(error.message, true);
      });
    }, 15000);
  }
}

busParentLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = new FormData(busParentLoginForm);
  try {
    await parentBusRequest("/api/bus/parent/login", {
      method: "POST",
      body: JSON.stringify({ accessCode: values.get("accessCode") }),
    });
    busParentLoginForm.reset();
    showParentBusMessage("");
    await refreshParentBusSession();
  } catch (error) {
    showParentBusMessage(error.message, true);
  }
});

document.querySelector("#bus-parent-logout").addEventListener("click", async () => {
  clearBusLocationPoll();
  try {
    await parentBusRequest("/api/bus/parent/logout", { method: "POST" });
    showParentBusMessage("You have signed out from live bus tracking.");
    await refreshParentBusSession();
  } catch (error) {
    showParentBusMessage(error.message, true);
  }
});

refreshParentBusSession().catch((error) => showParentBusMessage(error.message, true));

const staffLoginForm = document.querySelector("#staff-login-form");
const staffDashboard = document.querySelector("#staff-dashboard");
const staffConfigNotice = document.querySelector("#staff-config-notice");
const staffMessage = document.querySelector("#staff-message");
const enrollmentForm = document.querySelector("#enrollment-form");
const enrollmentClass = document.querySelector("#enrollment-class");
const enrollmentHouse = document.querySelector("#enrollment-house");
const enrollmentSchoolYear = document.querySelector("#enrollment-school-year");
const rosterRows = document.querySelector("#roster-rows");
const rosterTitle = document.querySelector("#roster-title");
const rosterCount = document.querySelector("#roster-count");
let studentHouses = [];

async function staffRequest(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    throw new Error(networkFailureMessage(error));
  }
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "The staff request could not be completed.");
  }
  return data;
}

function showStaffMessage(message, isError = false) {
  staffMessage.hidden = !message;
  staffMessage.textContent = message;
  staffMessage.classList.toggle("is-error", isError);
}

async function refreshStaffSession() {
  if (STATIC_DEMO) {
    return;
  }
  const session = await staffRequest("/api/staff/session");
  staffConfigNotice.hidden = session.enabled;
  staffLoginForm.hidden = !session.enabled || session.authenticated;
  staffDashboard.hidden = !session.authenticated;
  if (!staffLoginForm.hidden) {
    staffLoginForm.classList.add("is-visible");
  }
  if (!staffDashboard.hidden) {
    staffDashboard.classList.add("is-visible");
  }

  if (!session.enabled || !session.authenticated) {
    return;
  }

  enrollmentClass.replaceChildren(...session.classes.map((className) => {
    const option = document.createElement("option");
    option.value = className;
    option.textContent = className;
    return option;
  }));
  studentHouses = session.houses;
  enrollmentHouse.replaceChildren(...studentHouses.map((house) => {
    const option = document.createElement("option");
    option.value = house;
    option.textContent = `${house} house`;
    return option;
  }));
  enrollmentSchoolYear.replaceChildren(...session.schoolYears.map((schoolYear) => {
    const option = document.createElement("option");
    option.value = schoolYear;
    option.textContent = schoolYear;
    return option;
  }));
  document.querySelector("#achievement-class").replaceChildren(
    ...[...session.classes, "Class 10"].map((className) => {
      const option = document.createElement("option");
      option.value = className;
      option.textContent = className;
      return option;
    }),
  );
  await Promise.all([refreshRoster(), loadAchievements(), loadSchoolUpdates()]);
  await refreshStaffAchievements();
  refreshStaffSchoolUpdates();
}

function houseClassName(house) {
  return house ? `house-${house.toLowerCase()}` : "house-unassigned";
}

function createHouseSelect(houses, selectedHouse, student = null) {
  const select = document.createElement("select");
  select.className = `roster-house-select ${houseClassName(selectedHouse)}`;
  select.setAttribute(
    "aria-label",
    student ? `House for ${student.name}, student ID ${student.studentId}` : "Choose a house",
  );
  if (student) {
    select.dataset.rosterHouse = "true";
    select.dataset.studentId = student.studentId;
    select.dataset.studentName = student.name;
    select.dataset.savedHouse = selectedHouse || "";
    const unassigned = document.createElement("option");
    unassigned.value = "";
    unassigned.textContent = "Unassigned";
    select.append(unassigned);
  }
  houses.forEach((house) => {
    const option = document.createElement("option");
    option.value = house;
    option.textContent = `${house} house`;
    option.selected = house === selectedHouse;
    select.append(option);
  });
  return select;
}

async function refreshRoster() {
  const className = enrollmentClass.value;
  const academicYear = enrollmentSchoolYear.value;
  if (!className || !academicYear) {
    return;
  }
  const query = new URLSearchParams({ className, academicYear });
  const roster = await staffRequest(`/api/staff/roster?${query}`);
  rosterTitle.textContent = `${roster.className} · ${roster.academicYear}`;
  rosterCount.textContent = `${roster.students.length} / 60 students`;

  if (roster.students.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "No students enrolled in this class yet.";
    row.append(cell);
    rosterRows.replaceChildren(row);
    return;
  }

  rosterRows.replaceChildren(...roster.students.map((student) => {
    const row = document.createElement("tr");
    const rollCell = document.createElement("td");
    rollCell.textContent = student.rollNumber;
    const nameCell = document.createElement("td");
    nameCell.textContent = `${student.name} · ${student.studentId}`;
    const houseCell = document.createElement("td");
    houseCell.className = `roster-house-cell ${houseClassName(student.house)}`;
    houseCell.append(createHouseSelect(
      studentHouses,
      student.house,
      student,
    ));
    row.append(rollCell, nameCell, houseCell);
    return row;
  }));
}

const studentChatForm = document.querySelector("#student-chat-form");
const studentChatInput = document.querySelector("#student-chat-input");
const studentChatLog = document.querySelector("#student-chat-log");

function addStudentChatMessage(text, role = "assistant") {
  const message = document.createElement("p");
  message.className = `student-chat-message ${role}`;
  message.textContent = text;
  studentChatLog.append(message);
  return message;
}

function createStudentSearchResult(student) {
  const result = document.createElement("article");
  result.className = `student-search-result ${houseClassName(student.house)}`;
  const name = document.createElement("strong");
  name.textContent = student.name;
  const details = document.createElement("p");
  details.textContent = `${student.className} · Roll ${student.rollNumber} · ${student.academicYear}`;
  const id = document.createElement("code");
  id.textContent = `Student ID: ${student.studentId}`;
  const house = document.createElement("span");
  house.className = "student-search-house";
  house.textContent = student.house ? `${student.house} house` : "House not assigned";
  result.append(name, details, id, house);
  return result;
}

async function searchStudentsFromChat(query) {
  const parameters = new URLSearchParams({ q: query });
  const response = await staffRequest(`/api/staff/student-search?${parameters}`);
  if (!Array.isArray(response.students) || typeof response.hasMore !== "boolean") {
    throw new Error("The student finder returned an invalid response.");
  }
  if (!response.students.length) {
    addStudentChatMessage("I couldn’t find a matching enrolled student. Check the spelling, class, ID, or house assignment.");
    return;
  }

  addStudentChatMessage(
    `I found ${response.hasMore ? "at least " : ""}${response.hasMore ? "20" : response.students.length} matching enrolled student${response.students.length === 1 && !response.hasMore ? "" : "s"}.`,
  );
  const results = document.createElement("div");
  results.className = "student-search-results";
  results.setAttribute("aria-label", "Matching students");
  results.replaceChildren(...response.students.map(createStudentSearchResult));
  studentChatLog.append(results);
  if (response.hasMore) {
    addStudentChatMessage("Showing the first 20 matches. Add a name, class, or house to narrow your search.");
  }
}

studentChatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = studentChatInput.value.trim();
  if (!query) {
    return;
  }
  addStudentChatMessage(query, "user");
  const submitButton = studentChatForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  try {
    await searchStudentsFromChat(query);
    studentChatInput.value = "";
  } catch (error) {
    addStudentChatMessage(error.message);
  } finally {
    submitButton.disabled = false;
    studentChatLog.scrollTop = studentChatLog.scrollHeight;
    studentChatInput.focus();
  }
});

document.querySelectorAll("[data-student-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    studentChatInput.value = button.dataset.studentPrompt;
    studentChatForm.requestSubmit();
  });
});

rosterRows.addEventListener("change", async (event) => {
  const select = event.target.closest("[data-roster-house]");
  if (!select) {
    return;
  }
  const previousHouse = select.dataset.savedHouse;
  try {
    const result = await staffRequest("/api/staff/student-house", {
      method: "PUT",
      body: JSON.stringify({
        studentId: select.dataset.studentId,
        house: select.value,
      }),
    });
    select.dataset.savedHouse = result.house;
    select.className = `roster-house-select ${houseClassName(result.house)}`;
    select.closest("td").className = `roster-house-cell ${houseClassName(result.house)}`;
    showStaffMessage(`${select.dataset.studentName} assigned to ${result.house} house.`);
  } catch (error) {
    select.value = previousHouse;
    showStaffMessage(error.message, true);
  }
});

async function refreshStaffAchievements() {
  const list = document.querySelector("#staff-achievement-list");
  if (!schoolAchievements.length) {
    list.textContent = "No highlights are available.";
    return;
  }
  list.replaceChildren(...schoolAchievements.map((achievement) => {
    const item = document.createElement("div");
    item.className = "staff-achievement-item";
    const text = document.createElement("span");
    text.textContent = `${achievementSportNames[achievement.sport]} · ${achievement.title} · ${achievement.className}`;
    item.append(text);
    if (!achievement.isSample) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "staff-logout";
      remove.dataset.deleteAchievement = String(achievement.achievementId);
      remove.textContent = "Remove";
      item.append(remove);
    } else {
      const sample = document.createElement("small");
      sample.textContent = "Sample";
      item.append(sample);
    }
    return item;
  }));
}

const staffFeeList = document.querySelector("#staff-fee-list");
staffFeeList.addEventListener("submit", async (event) => {
  const form = event.target.closest(".staff-fee-form");
  if (!form) {
    return;
  }
  event.preventDefault();
  const values = new FormData(form);
  try {
    await staffRequest("/api/staff/fees", {
      method: "PUT",
      body: JSON.stringify({
        feeId: form.dataset.feeId,
        amount: Number(values.get("amount")),
        isConfirmed: values.has("isConfirmed"),
      }),
    });
    await loadFeeSchedule();
    showStaffMessage("The fee schedule has been saved.");
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

document.querySelector("#achievement-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  try {
    await staffRequest("/api/staff/achievements", {
      method: "POST",
      body: JSON.stringify({
        sport: values.get("sport"),
        className: values.get("className"),
        title: values.get("title"),
        award: values.get("award"),
      }),
    });
    form.reset();
    await loadAchievements();
    await refreshStaffAchievements();
    showStaffMessage("The school activity highlight has been saved.");
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

document.querySelector("#staff-achievement-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-achievement]");
  if (!button) {
    return;
  }
  try {
    await staffRequest("/api/staff/achievements", {
      method: "DELETE",
      body: JSON.stringify({ achievementId: Number(button.dataset.deleteAchievement) }),
    });
    await loadAchievements();
    await refreshStaffAchievements();
    showStaffMessage("The activity highlight has been removed.");
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

staffLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = new FormData(staffLoginForm);
  try {
    await staffRequest("/api/staff/login", {
      method: "POST",
      body: JSON.stringify({
        username: values.get("username"),
        password: values.get("password"),
      }),
    });
    staffLoginForm.reset();
    showStaffMessage("");
    await refreshStaffSession();
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

enrollmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = new FormData(enrollmentForm);
  try {
    const student = await staffRequest("/api/staff/enroll", {
      method: "POST",
      body: JSON.stringify({
        name: values.get("name"),
        className: values.get("className"),
        academicYear: values.get("academicYear"),
        house: values.get("house"),
      }),
    });
    showStaffMessage(
      `${student.name} enrolled in ${student.className} for ${student.academicYear} with roll number ${student.rollNumber} in ${student.house} house. Student ID: ${student.studentId}.`
    );
    document.querySelector("#enrollment-name").value = "";
    await refreshRoster();
    document.querySelector("#enrollment-name").focus();
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

document.querySelector("#staff-logout").addEventListener("click", async () => {
  stopBusGpsWatch();
  try {
    await busGpsUpdateQueue;
    await staffRequest("/api/staff/logout", { method: "POST" });
    showStaffMessage("You have been signed out.");
    await refreshStaffSession();
  } catch (error) {
    showStaffMessage(error.message, true);
  }
});

enrollmentClass.addEventListener("change", () => {
  refreshRoster().catch((error) => showStaffMessage(error.message, true));
});
enrollmentSchoolYear.addEventListener("change", () => {
  refreshRoster().catch((error) => showStaffMessage(error.message, true));
});

refreshStaffSession().catch((error) => showStaffMessage(error.message, true));

window.addEventListener("pagehide", () => {
  clearBusLocationPoll();
  stopBusGpsWatch();
});

const studentForm = document.querySelector("#student-form");
const studentIdInput = document.querySelector("#student-id");
const studentResult = document.querySelector("#student-result");
const alumniTotal = document.querySelector("#alumni-total");
const alumniChart = document.querySelector("#alumni-chart");

async function loadAlumniBatches() {
  try {
    let data;
    if (STATIC_DEMO) {
      data = {
        batches: [
          { year: 2019, graduates: 15 },
          { year: 2020, graduates: 30 },
          { year: 2021, graduates: 45 },
          { year: 2022, graduates: 45 },
          { year: 2023, graduates: 50 },
          { year: 2024, graduates: 60 },
          { year: 2025, graduates: 60 },
          { year: 2026, graduates: 60 },
        ],
        totalGraduates: 365,
      };
    } else {
      const response = await fetch("/api/alumni-batches");
      if (!response.ok) {
        throw new Error(`Alumni-batch request failed with status ${response.status}`);
      }
      data = await response.json();
    }
    if (
      !Array.isArray(data.batches)
      || !Number.isInteger(data.totalGraduates)
      || data.batches.some((batch) => (
        !Number.isInteger(batch.year)
        || !Number.isInteger(batch.graduates)
        || batch.graduates < 0
      ))
      || data.totalGraduates !== data.batches.reduce(
        (total, batch) => total + batch.graduates,
        0
      )
    ) {
      throw new Error("The alumni-batch response has an invalid format.");
    }

    const largestBatch = Math.max(...data.batches.map((batch) => batch.graduates), 1);
    const columns = data.batches.map((batch) => {
      const column = document.createElement("div");
      column.className = "alumni-bar-column";
      column.setAttribute("role", "listitem");
      column.setAttribute("aria-label", `${batch.year}: ${batch.graduates} students passed out`);

      const count = document.createElement("span");
      count.className = "alumni-bar-count";
      count.textContent = batch.graduates;

      const track = document.createElement("span");
      track.className = "alumni-bar-track";
      const bar = document.createElement("span");
      bar.className = "alumni-bar";
      bar.style.setProperty("--bar-height", `${(batch.graduates / largestBatch) * 100}%`);
      track.append(bar);

      const year = document.createElement("span");
      year.className = "alumni-bar-year";
      year.textContent = batch.year;
      column.append(count, track, year);
      return column;
    });

    alumniTotal.textContent = data.totalGraduates.toLocaleString("en-IN");
    alumniChart.replaceChildren(...columns);
  } catch (error) {
    noteServerUnavailable(error);
    console.error("Could not load the Sage graduating-batch counts.", error);
    alumniTotal.textContent = "—";
    alumniChart.textContent = "Graduating-batch details are unavailable.";
  }
}

loadAlumniBatches();

document.querySelectorAll(".sample-id").forEach((button) => {
  button.addEventListener("click", () => {
    studentIdInput.value = button.dataset.id;
    studentIdInput.focus();
  });
});

studentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (STATIC_DEMO) {
    return;
  }
  studentResult.hidden = false;
  studentResult.className = "student-result";
  studentResult.textContent = "Checking the demo record…";

  try {
    const response = await fetch(`/api/student?id=${encodeURIComponent(studentIdInput.value.trim())}`);
    const data = await response.json();
    if (!response.ok) {
      studentResult.classList.add("error");
      studentResult.innerHTML = "<h3>No demo record found</h3><p>Check the ID and try one of the sample IDs shown.</p>";
      return;
    }

    const statusClass = data.status === "Alumni" ? "alumni" : "";
    studentResult.innerHTML = `<span class="status-pill ${statusClass}">${escapeHtml(data.status)}</span><h3>${escapeHtml(data.name)}</h3><p>${escapeHtml(data.class_name)}${data.graduation_year ? ` · Graduated ${data.graduation_year}` : ""}<br>Student ID: ${escapeHtml(data.student_id)}</p>`;
  } catch (error) {
    noteServerUnavailable(error);
    studentResult.classList.add("error");
    studentResult.innerHTML = "<h3>Couldn’t check that record</h3><p>Please make sure the school website is running, then try again.</p>";
  }
});

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}
