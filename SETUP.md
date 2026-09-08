# Setting this up without writing any code

You will not type a single line of code. You will click through a website
twice, and then it runs by itself every weekday evening.

Set aside 30 minutes. Use a laptop or desktop, not a phone.

---

## Before you start

Unzip the file you downloaded. You should see a folder containing `screener`,
`state`, `docs`, a `.github` folder, and several files including
`requirements.txt` and `universe.csv`. Keep this window open.

---

## Step 1 — Make a GitHub account

Go to github.com and sign up. It is free. Verify your email.

## Step 2 — Make a place for the system to live

Click the **+** at the top right, then **New repository**.

- Repository name: `momentum` (or anything)
- Select **Private**
- Do not tick any of the boxes underneath
- Click **Create repository**

## Step 3 — Upload the files

On the page that appears, click **uploading an existing file**.

Open your unzipped folder. Select everything inside it — but **not** the
`.github` folder, which we handle next. Drag it all into the browser window.

Scroll down, click **Commit changes**. Wait for the upload to finish.

## Step 4 — Add the one file that cannot be dragged

GitHub's uploader skips folders whose name starts with a dot, so this one file
has to be created by hand. It is copy and paste, nothing more.

1. Click **Add file**, then **Create new file**.
2. In the filename box, type exactly this, including the slashes:
   ```
   .github/workflows/momentum.yml
   ```
   The box will split into folders as you type the slashes. That is correct.
3. In your unzipped folder, open `.github/workflows/momentum.yml` with Notepad
   (Windows) or TextEdit (Mac). Select all, copy.
4. Paste it into the big empty box on GitHub.
5. Click **Commit changes**.

## Step 5 — Give it permission to save its own results

Click **Settings** (top of your repository), then **Actions** in the left
sidebar, then **General**.

Scroll to **Workflow permissions**. Select **Read and write permissions**.
Click **Save**.

Without this the system runs but cannot remember what you own.

## Step 6 — Turn on the web page

Still in **Settings**, click **Pages** in the left sidebar.

Under Source choose **Deploy from a branch**. Set the branch to `main` and the
folder to `/docs`. Click **Save**.

It will show you a web address. Write it down. That is your dashboard.

## Step 7 — Run it for the first time

Click the **Actions** tab at the top. If it asks whether to enable workflows,
say yes.

In the left sidebar click **Momentum run**, then the **Run workflow** button on
the right. Leave **Force rebalance** unticked for now. Click the green
**Run workflow**.

A yellow dot appears. It becomes a green tick when finished. This run takes
20 to 30 minutes.

## Step 8 — Let it finish loading, then build your book

Company data is fetched a few hundred names at a time on purpose, so the run
never times out and Yahoo never blocks it. That means the market loads over
three or four runs, not one.

Open your dashboard after the first run. The banner at the top will be orange
and say how many companies are still to load. **This is normal.** While it says
that, the system deliberately refuses to pick your 20 stocks, because a book
chosen from a third of the market is not the best book.

Run the workflow again (same button, Force rebalance still unticked). Repeat
until the orange banner is gone and the top of the dashboard turns blue.
Usually three or four runs. You can run them back to back on the same day.

Once the banner is blue, run the workflow one final time with **Force
rebalance ticked**. That builds your opening 20 and they appear under
**Entering** with the weight and stop price for each.

That is your day one list. Bookmark the dashboard on your phone.

---

## From now on

It runs by itself at 17:45 IST every weekday. You do nothing.

Open the dashboard when you want. The top of the page tells you the market
regime, then what to sell, then what to buy, then anything that newly qualified
today.

## The two files you should keep updated

Both are edited on the GitHub website — click the file, click the pencil icon,
type, click Commit changes.

**`catalysts.csv`** — add a row whenever a company announces something
important. An order win, new capacity, a big contract. Format:

```
symbol,note,date
KAYNES,Rs 1400 cr order win,2026-08-20
```

This is the highest-weighted input in the whole system. It is the one place
your judgement enters, and it is worth more than any of the maths.

**`themes.csv`** — your sunrise sectors. Edit the weights as your view changes.

## When something goes wrong

The Actions tab will show a red X instead of a green tick.

1. Click the red X.
2. Click the step that failed.
3. Select the error text and copy it.
4. Send it to whoever is helping you.

Nothing is broken permanently. A failed run simply means the dashboard shows
yesterday's numbers until the next run succeeds.

## Two settings you may want to change later

Click `screener/config.py` on GitHub, click the pencil, change the number,
commit. Do not change anything else in that file.

- `INITIAL_STOP` — currently `0.10`. If you find you are being stopped out of
  names that then recover, change it to `0.15`.
- `MAX_EXT_20DMA` — currently `0.12`. If the Entering list is regularly empty
  in a strong market, change it to `0.18`.

## What you still have to do yourself

The system tells you what to buy and sell. It does not place orders. When it
says buy, you buy. When it says sell, you sell. When you buy, also place a
good-till-triggered stop with your broker at the stop price shown, so the 10%
rule protects you even if you do not open the dashboard for a week.
