# Implementing Features From Your Phone

Create GitHub issues from your phone and have Claude automatically implement
them on the Dell server. Test changes live on the PWA, give feedback, iterate
— all without touching your laptop.

## How It Works

A poller on the Dell checks GitHub every 5 minutes for issues labeled `claude`.
When it finds one, it runs Claude Code CLI (Opus model, using your subscription
— no API costs) to implement the feature, then auto-deploys the branch so you
can test immediately on your phone.

```
You (phone)                         Dell server
───────────                         ───────────
1. Create issue, add               Poller detects (≤5 min)
   'claude' label            →     Claude reads the codebase,
                                    implements, runs tests

2.                           ←     Branch deployed to your phone
                                    Label → claude-review
                                    Comment with PR link

3. Test on your phone
   Open the app, try the
   feature

4a. Not right? Comment      →     Claude reads your feedback,
    feedback on the issue           iterates, redeploys
                                    (back to step 2)

4b. Looks good? Comment     →     PR merged, main deployed
    'lgtm'                          Label → claude-done
```

## Step-by-Step

### 1. Create the Issue

Open GitHub mobile and create a new issue on the HealthApp repo.

**Write a good issue:**
- Be specific about what you want: *"Add a rest timer to the workout page
  that counts down from the configured rest period and vibrates when done"*
  works much better than *"add timer"*
- Describe what you see in text — Claude cannot view attached images
- Mention relevant files or pages if you know them
- One feature or fix per issue

**Example issues that work well:**
- "The body battery chart shows straight lines between points — make them
  smooth curves like the Garmin Connect app"
- "Add a weekly step count summary card to the dashboard showing total steps,
  daily average, and best day"
- "The food log date picker doesn't work on iOS Safari — tapping it does nothing"

**Example issues that don't work well:**
- "fix the app" (too vague)
- "make it look better" (no specific direction)
- [screenshot with no text] (Claude can't see images)

### 2. Add the `claude` Label

On the issue, tap the gear icon next to "Labels" and select `claude`.
This triggers the poller to pick it up.

### 3. Wait for Claude

Within 5 minutes, the poller picks up the issue. You'll see:
- Label changes to `claude-wip` (working)
- A comment: "Poller picked up this issue. Claude is working on it now..."

Claude typically takes 5–30 minutes depending on complexity. It will:
- Read the codebase and understand the current state
- Implement the feature or fix
- Run backend tests and frontend lint
- Create a git branch and open a PR

### 4. Test on Your Phone

When Claude finishes, the feature branch is **automatically deployed** to the
Dell. You'll see:
- Label changes to `claude-review`
- A comment: "Changes are live on your phone for testing"

**Kill and reopen the PWA** on your phone (swipe it away, then tap the icon
again) to pick up the new service worker. Then test the feature.

### 5. Give Feedback or Approve

**If it needs changes:** Comment on the issue with specific feedback.

Good feedback examples:
- "The chart line should be curved, not straight"
- "The button works but it's too small to tap on mobile — make it at least 44px"
- "The timer counts down but doesn't vibrate when it hits zero"

Claude will pick up your feedback within 5 minutes, make changes, and redeploy.
You can go back and forth up to 10 rounds.

**If it looks good:** Comment `lgtm` on the issue.

The poller will merge the PR, deploy main, and label the issue `claude-done`.

## Labels Reference

| Label | Meaning |
|-------|---------|
| `claude` | Ready for Claude to pick up |
| `claude-wip` | Claude is actively working |
| `claude-waiting` | Claude asked a question — reply to continue |
| `claude-review` | Changes deployed, waiting for your feedback |
| `claude-done` | Merged and deployed |
| `claude-failed` | Something went wrong — check the comment |

## What If...

**Claude asks a question instead of implementing?**
The label changes to `claude-waiting` and Claude's question appears as a
comment. Reply to the issue and the poller resumes automatically.

**Claude fails?**
The label changes to `claude-failed` and an error comment is posted. Read the
error, then remove `claude-failed` and re-add `claude` to retry (optionally
update the issue description with more detail).

**You hit the usage limit?**
The poller detects rate limits and waits 2 hours before retrying automatically.
The issue label reverts to `claude` so it gets picked up again once usage
refreshes. You don't need to do anything.

**The poller is down?**
If the Dell was rebooted, the poller auto-starts at logon. Issues labeled
`claude` will be picked up on the next poll cycle. Issues that were
`claude-review` will have their branches re-deployed.

**You want to cancel?**
Remove all `claude-*` labels from the issue. The poller ignores issues without
these labels.

**Multiple issues at once?**
Claude works on them one at a time (sequentially). Label multiple issues with
`claude` and they'll be processed in order.

## Tips

- **Be specific over brief.** A detailed 3-sentence issue gets a better
  result than a vague 3-word one.
- **Mention the page or component** if you know it: "on the Body Battery
  drill-down page" or "in the workout log".
- **Give visual feedback** in words: "the spacing is too tight", "the color
  should be blue not grey", "the chart should look like Garmin Connect's
  stress chart".
- **One thing at a time.** Smaller, focused issues produce better results
  than large multi-part requests.
- **Review rounds are cheap.** It's better to start with a rough issue and
  refine via feedback than to try to write the perfect issue upfront.
