using System;
using System.Linq;
using UnityEngine;
using Verse;

namespace RimWorldDevTests;

// Read-only view of the current report. The runner never waits for this panel to draw.
internal static class TestPresentation
{
    private sealed class Row
    {
        public string Id, Name, Visible;
        public float TextWidth;
    }
    private static Progress progress;
    private static Batch batch;
    private static Row[] rows = Array.Empty<Row>();
    private static float fittedWidth;
    private static int totalTests;
    private static Vector2 scroll;
    private static string followed;
    private static bool enabled;
    private static readonly Color Muted = new(0.61f, 0.64f, 0.68f);
    private static readonly Color Passed = new(0.48f, 0.88f, 0.57f);
    private static readonly Color Failed = new(1f, 0.47f, 0.43f);
    private static readonly Color Skipped = new(0.94f, 0.76f, 0.43f);
    private const float RowHeight = 26;
    private const float Margin = 12;
    private static float PanelWidth => UI.screenWidth * 0.15f;
    internal static float ReservedWidthFraction => enabled ? (PanelWidth + 2 * Margin) / UI.screenWidth : 0;

    public static void Reset(bool enable)
    {
        enabled = enable;
        progress = null; batch = null; rows = Array.Empty<Row>();
        scroll = Vector2.zero; followed = null; fittedWidth = 0;
        totalTests = 0;
    }

    public static void Changed(Progress current, Batch currentBatch)
    {
        if (!enabled) return;
        progress = current;
        if (totalTests == 0) totalTests = current.Request.Batches.Sum(id => Batches.All[id].Plan.Count);
        if (batch == currentBatch) return;
        batch = currentBatch;
        rows = batch.Plan.Select(p => new Row { Id = p.Id, Name = ShortName(p.Id, batch.Id) }).ToArray();
        scroll = Vector2.zero; followed = null; fittedWidth = 0;
    }

    private static string Words(string id)
    {
        string text = id.Replace('.', ' ').Replace('-', ' ');
        return char.ToUpperInvariant(text[0]) + text[1..];
    }

    private static string ShortName(string id, string batchId)
    {
        if (Harness.Settings.ShortCaseName(id, batchId) is { } custom) return custom;
        if (id.StartsWith(batchId + ".", StringComparison.Ordinal)) id = id[(batchId.Length + 1)..];
        return Words(id);
    }

    private static string Fit(string text, float width, bool bold = false)
    {
        string Measure(string value) => bold ? "<b>" + value + "</b>" : value;
        if (Text.CalcSize(Measure(text)).x <= width) return text;
        while (text.Length > 0 && Text.CalcSize(Measure(text + "…")).x > width) text = text[..^1];
        return text.Length == 0 ? "" : text.TrimEnd() + "…";
    }

    public static void Draw()
    {
        if (!enabled || progress == null || batch == null || Current.ProgramState != ProgramState.Playing ||
            !RunnerIdentity.Owned(Current.Game)) return;
        var oldFont = Text.Font;
        var oldAnchor = Text.Anchor;
        var oldWrap = Text.WordWrap;
        var oldColor = GUI.color;
        try
        {
            Text.Font = GameFont.Tiny; Text.Anchor = TextAnchor.UpperLeft; Text.WordWrap = false;
            float width = PanelWidth;
            float height = Math.Min(UI.screenHeight * 0.55f, 124 + rows.Length * RowHeight);
            var panel = new Rect(UI.screenWidth - width - Margin, UI.screenHeight - height - Margin, width, height);
            Widgets.DrawBoxSolid(panel, new Color(0.05f, 0.06f, 0.08f, 0.96f));
            var results = progress.Cases.Where(c => c.Batch == batch.Id).ToDictionary(c => c.Id);
            var active = results.Values.LastOrDefault(c => c.Result == Results.Running);
            var latest = results.Values.LastOrDefault();
            bool complete = progress.BatchRecords.LastOrDefault(b => b.Id == batch.Id)?.Status != RunStatus.Running;
            GUI.color = Color.white;
            float innerWidth = width - 20;
            int number = progress.Request.Batches.IndexOf(batch.Id) + 1;
            int completedTests = progress.Cases.Count(c => c.Result is Results.Pass or Results.Fail or Results.Skip or Results.Error);
            Widgets.Label(new Rect(panel.x + 10, panel.y + 8, innerWidth, 22),
                $"<b>Batch {number}/{progress.Request.Batches.Count} ({completedTests}/{totalTests} tests)</b>");
            Widgets.Label(new Rect(panel.x + 10, panel.y + 28, innerWidth, 22), Fit(Words(batch.Id), innerWidth));
            string status = active != null ? "Testing…" : complete ? "Batch complete" : "Preparing test setup…";
            Widgets.Label(new Rect(panel.x + 10, panel.y + 48, innerWidth, 22), Fit(status, innerWidth));
            int pass = results.Values.Count(c => c.Result == Results.Pass);
            int fail = results.Values.Count(c => c.Result is Results.Fail or Results.Error);
            int skip = results.Values.Count(c => c.Result == Results.Skip);
            GUI.color = Muted;
            Widgets.Label(new Rect(panel.x + 10, panel.y + 70, innerWidth, 22),
                Fit($"{pass} pass / {fail} fail / {skip} skip", innerWidth));
            var viewport = new Rect(panel.x + 6, panel.y + 98, width - 12, height - 106);
            var content = new Rect(0, 0, viewport.width - 18, rows.Length * RowHeight);
            float labelWidth = Math.Max(0, content.width - 29);
            if (fittedWidth != labelWidth)
            {
                foreach (var row in rows)
                {
                    row.Visible = Fit(row.Name, labelWidth, bold: true);
                    row.TextWidth = Text.CalcSize(row.Visible).x;
                }
                fittedWidth = labelWidth;
            }
            string target = active?.Id ?? latest?.Id;
            if (target != followed)
            {
                int index = Array.FindIndex(rows, r => r.Id == target);
                scroll.y = Mathf.Clamp(index * RowHeight - viewport.height / 2, 0, Math.Max(0, content.height - viewport.height));
                followed = target;
            }
            Widgets.BeginScrollView(viewport, ref scroll, content);
            try
            {
                int first = Math.Max(0, (int)(scroll.y / RowHeight));
                int last = Math.Min(rows.Length, (int)Math.Ceiling((scroll.y + viewport.height) / RowHeight));
                for (int i = first; i < last; i++)
                {
                    var row = rows[i];
                    results.TryGetValue(row.Id, out var result);
                    bool running = result?.Result == Results.Running;
                    bool finished = result?.Result is Results.Pass or Results.Fail or Results.Error;
                    Color color = result?.Result == Results.Pass ? Passed : result?.Result is Results.Fail or Results.Error ? Failed
                        : result?.Result == Results.Skip ? Skipped : running ? Color.white : Muted;
                    float y = i * RowHeight;
                    if (running) Widgets.DrawBoxSolid(new Rect(0, y, content.width, RowHeight), new Color(0.16f, 0.19f, 0.23f));
                    GUI.color = color;
                    var box = new Rect(3, y + 5, 16, 16);
                    Widgets.DrawBox(box);
                    if (result?.Result == Results.Pass)
                    {
                        Widgets.DrawLine(new Vector2(box.x + 3, box.y + 8), new Vector2(box.x + 7, box.y + 12), color, 2);
                        Widgets.DrawLine(new Vector2(box.x + 7, box.y + 12), new Vector2(box.x + 14, box.y + 3), color, 2);
                    }
                    else if (result?.Result is Results.Fail or Results.Error)
                    {
                        Widgets.DrawLine(new Vector2(box.x + 4, box.y + 4), new Vector2(box.x + 12, box.y + 12), color, 2);
                        Widgets.DrawLine(new Vector2(box.x + 12, box.y + 4), new Vector2(box.x + 4, box.y + 12), color, 2);
                    }
                    else if (result?.Result == Results.Skip) Widgets.DrawBoxSolid(new Rect(box.x + 4, box.y + 7, 8, 2), color);
                    string suffix = result?.Result == Results.Error ? " [Error]" : result?.Result == Results.Skip ? " [Skipped]" : "";
                    string visible = suffix.Length == 0 ? row.Visible : Fit(row.Name, labelWidth - Text.CalcSize(suffix).x) + suffix;
                    var label = new Rect(24, y + 1, labelWidth, 24);
                    Widgets.Label(label, running ? "<b>" + visible + "</b>" : visible);
                    if (finished) Widgets.DrawBoxSolid(new Rect(label.x, label.y + 10,
                        suffix.Length == 0 ? row.TextWidth : Text.CalcSize(visible).x, 1), color);
                }
            }
            finally { Widgets.EndScrollView(); }
        }
        finally { Text.Font = oldFont; Text.Anchor = oldAnchor; Text.WordWrap = oldWrap; GUI.color = oldColor; }
    }
}
