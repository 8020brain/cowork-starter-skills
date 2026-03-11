---
name: draft-post
description: Creates polished social media posts from rough input, voice notes, or ideas. Handles LinkedIn and X/Twitter with platform-specific formatting. Pairs with the post-evaluator skill for a full content quality pipeline with scoring, iterative rewrites, and cross-platform adaptation. Use when the user says "write a post", "draft a post", "content pipeline", or provides content to turn into a post.
---

# Draft Post Skill

## Your Task

Transform rough ideas, voice notes, or text into polished, platform-specific social media posts that sound like a real person wrote them, not an AI.

**Outputs (per run):**
1. **LinkedIn post** - formatted for the platform, medium length
2. **X/Twitter post** - concise, punchy, fits the platform's style

You may produce one or both depending on what the user asks for. Default to both.

## Reference Files

**Read these bundled reference files before drafting:**
1. `references/tone-guide.md` - The user's voice, banned words, preferred style
2. `references/post-writing-guide.md` - Platform formatting rules and writing principles

## Process

### Step 1: Analyse Input

When invoked with text (from voice note, rough idea, or direct input):
1. Read the reference files above
2. Analyse the input to determine:
   - **Topic**: What is the post about?
   - **Key themes**: Main points to communicate
   - **Angle**: What makes this take interesting or different?
   - **Hook**: What's the punchy opening that stops the scroll?

### Step 2: Clean the Input (if from voice note)

If the input is a raw transcript or voice note:
- Remove filler words, false starts, repetitions
- Fix grammar and organise thoughts
- Keep ALL substantive content, natural voice, and energy
- The result should read as if the person had perfect articulation, but it's still clearly them talking

### Step 3: Create Post Versions

Create posts for the requested platforms (default: both LinkedIn and X).

**LinkedIn Post:**
- Use separators: `---`
- Use arrows for bullet points: `->`
- Keep to ~50 lines max
- No hashtags, limited emojis
- Lead with the insight or result
- Format for readability: short paragraphs, white space, scannable structure

**X/Twitter Post:**
- 280 characters max for a single post
- If the idea needs more room, structure as a thread (numbered posts)
- Each thread post should stand alone but flow together
- Punchy, direct, conversational
- No hashtags unless specifically requested
- First post is the hook, it must work on its own

### Step 4: Apply the User's Voice

**Apply from reference files:**
- Voice rules from `tone-guide.md`
- Short sentences (5-15 words), conversational, concrete examples
- Opening with punch: strong declarative statement
- Single-word sentences for impact
- Personal stories and real experience
- End with action or clear takeaway

**If tone-guide.md has not been customised yet**, apply these universal defaults:
- Write like a person, not a brand
- Direct and conversational
- Concrete over abstract
- No corporate speak or buzzwords
- Contractions are fine (I'm, can't, you're)

### Step 5: Save Posts

**Filename format**: `[platform]-YYYYMMDD-descriptive-topic.md`

Save posts to the current project's content or posts folder. If no obvious location exists, save to the current working directory.

Each file gets a metadata comment at top:
```markdown
<!-- DRAFT - Generated on YYYY-MM-DD -->
<!-- Platform: [LinkedIn/X] -->
<!-- Topic: [Brief description] -->
```

### Step 6: Self-Review (Quality Check)

Before showing the user, review each post against this checklist:

**Content quality:**
- [ ] Does the hook stop the scroll? Would YOU stop scrolling for this?
- [ ] Is there a concrete example, number, or specific detail?
- [ ] Does it end with a clear takeaway or call to action?
- [ ] Is every sentence earning its place? Cut anything that doesn't add value.

**Voice quality:**
- [ ] Does it sound like a real person or like AI marketing copy?
- [ ] Are sentences short and punchy (5-15 words mostly)?
- [ ] No banned words or AI-isms? (check tone-guide.md)
- [ ] Written to ONE person ("you"), not a crowd?

**Platform formatting:**
- [ ] LinkedIn: separators, arrows, white space, ~50 lines max?
- [ ] X: under 280 chars (single) or clean thread structure?

**If any check fails, fix it before showing the user.**

### Step 7: Present to User

Show the user the draft posts and ask for feedback. Common next steps:
- Edit tone or angle
- Shorten or expand
- Change the hook
- Add or remove a CTA
- Generate for additional platforms

---

## Pipeline Mode

**When the user mentions BOTH draft-post and post-evaluator together, or asks for a "content pipeline", ALWAYS run the full pipeline. Never stop at just the first draft.**

Pipeline Mode transforms a single content idea into a fully polished, multi-platform post through automated scoring, targeted rewrites, hook exploration, and cross-platform adaptation. Here is the full workflow:

### Pipeline Step 1: Write Initial Draft (Steps 1-5 above)

Write the first draft using the standard process above. Save it as the initial version. This becomes the "BEFORE" version for the final comparison.

### Pipeline Step 2: Score with Post-Evaluator

Invoke the **post-evaluator** skill to score the draft across all 5 evaluation lenses:
- **Clarity** (threshold: 70) - Can a busy person get the point in 10 seconds?
- **Voice** (threshold: 75) - Does it sound like a real person, not AI?
- **Hook** (threshold: 65) - Would you stop scrolling?
- **Substance** (threshold: 70) - Concrete takeaway an expert would respect?
- **Platform Fit** (threshold: 70) - Correct formatting for the target platform?

Show the score breakdown to the user in a clear table:

```
| Lens         | Score | Threshold | Result |
|--------------|-------|-----------|--------|
| Clarity      |  82   |    70     |   PASS |
| Voice        |  68   |    75     |   FAIL |
| Hook         |  71   |    65     |   PASS |
| Substance    |  74   |    70     |   PASS |
| Platform Fit |  85   |    70     |   PASS |
```

### Pipeline Step 3: Iterative Rewrite of Failing Lenses

For any lens that scores BELOW its threshold:
1. Read the specific `rewriteGuidance` from the post-evaluator output
2. Rewrite ONLY the aspect that failed (do not touch what is already passing)
3. Re-score ONLY the rewritten lens (keep other scores as they were)
4. Repeat up to 3 iterations per failing lens
5. If a lens still fails after 3 iterations, keep the best-scoring version and move on

**Key rule:** Fixing one lens must not break another. If a Voice rewrite drops Clarity below threshold, revert and try a different approach.

### Pipeline Step 4: Generate 3 Hook Variations

Once all lenses pass (or after max iterations), generate 3 ALTERNATIVE HOOKS for the opening. Each hook MUST use a fundamentally different approach:

1. **Question hook** - Opens with a provocative or recognition-triggering question the reader can't ignore
2. **Bold statement hook** - Opens with a surprising claim, contrarian take, or hard number that demands attention
3. **Story/anecdote hook** - Opens with a micro-story, specific moment, or vivid scene that pulls the reader in

Present all 3 hooks alongside the current opening so the user can compare and pick the strongest opener. Label each clearly with its approach.

**The 3 hook variations must be GENUINELY different approaches, not just rewording the same hook.** A question, a bold statement, and a story opener should feel like completely different entry points into the same post.

### Pipeline Step 5: Adapt for X/Twitter

Take the winning version (after all lenses pass) and adapt it for X/Twitter:
- If the content fits in 280 characters, create a single tweet
- If it needs more room, structure as a thread (5-10 posts)
- Each thread post must stand alone but flow together
- The first post IS the hook, it must work completely on its own
- Maintain the voice and substance, compress the structure

### Pipeline Step 6: Before/After Comparison

Show a side-by-side comparison of:
- **BEFORE**: The original first draft (from Pipeline Step 1), exactly as written
- **AFTER**: The final polished version (after all lens rewrites and improvements)

Highlight what changed and why. This lets the user see exactly how the pipeline improved the post.

### Pipeline Step 7: Save All Versions

Save all versions to an output/ folder (create if needed):
- `output/[topic]-v1-initial.md` - Original first draft
- `output/[topic]-v2-final-linkedin.md` - Final polished LinkedIn version
- `output/[topic]-v2-final-x.md` - Final X/Twitter version
- `output/[topic]-hooks.md` - All 3 hook variations

---

## Quality Principles

These principles separate good posts from AI slop:

1. **Lead with the insight, not the setup.** Don't build up to the point. Start with it.
2. **One idea per post.** If you have three ideas, that's three posts.
3. **Specific beats general.** "I tested 47 headlines" beats "I tested a lot of headlines."
4. **Show, don't tell.** Don't say something is important. Show why it matters.
5. **Write to one person.** Never "some of you" or "many people." Always "you."
6. **Earn every sentence.** If a sentence doesn't add value, cut it.
7. **End with action.** Give the reader something to do, think about, or try.

## Error Handling

- **Insufficient content**: Ask for more details before proceeding
- **Multiple topics**: Ask if the user wants separate posts or wants to focus on one
- **No tone guide customised**: Use sensible defaults (direct, conversational, no jargon)
- **Platform not specified**: Default to LinkedIn + X
- **Post-evaluator not available**: If running pipeline mode and the post-evaluator skill is not installed, fall back to the built-in self-review (Step 6) and note that full scoring requires the post-evaluator skill

## Expected Output

**Standard mode:** 2 ready-to-use post files (LinkedIn + X), each optimised for its platform.

**Pipeline mode:** Full content quality package:
1. Scored and polished LinkedIn post (all 5 lenses passing)
2. 3 alternative hook variations
3. X/Twitter adaptation (single post or thread)
4. Before/after comparison showing the improvement
5. All versions saved to output/
