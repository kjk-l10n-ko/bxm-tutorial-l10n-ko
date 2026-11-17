using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mono.Cecil;
using Mono.Cecil.Cil;

namespace DllPatch;

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private static int Main(string[] args)
    {
        try
        {
            return args.Length > 0
                ? args[0] switch
                {
                    "dump" => Dump(args[1..]),
                    "patch" => Patch(args[1..]),
                    _ => Usage(),
                }
                : Usage();
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"error: {e.Message}");
            return 1;
        }
    }

    private static int Usage()
    {
        Console.Error.WriteLine("""
            usage:
              dllpatch dump  --dll <Assembly-CSharp.dll> --out <json> [--strings <curated.json>] [--raw]
              dllpatch patch --dll <in.dll> --map <json> --out <out.dll> [--strings <strings.json>]
            """);
        return 2;
    }

    // ---------------- dump ----------------

    private static int Dump(string[] args)
    {
        var a = ParseArgs(args, "dll", "out");
        bool raw = args.Contains("--raw");
        string curatedPath = a.GetValueOrDefault("strings") ?? "scripts/dllpatch/strings.json";
        var found = Scan(a["dll"]);

        if (raw)
        {
            var rawList = found.Select(f => new Entry { Id = f.Id, Zh = f.Zh }).ToList();
            WriteJson(a["out"], rawList);
            Console.WriteLine($"dump(raw): {rawList.Count} CJK ldstr literals -> {a["out"]}");
            return 0;
        }

        if (!File.Exists(curatedPath))
            throw new FileNotFoundException($"curated strings file not found: {curatedPath}");
        var curated = JsonSerializer.Deserialize<Curated>(File.ReadAllText(curatedPath), JsonOpts)
                      ?? throw new InvalidDataException("empty curated file");

        var foundIds = found.Select(f => f.Id).ToHashSet();
        var includeIds = curated.Include.Keys.ToHashSet();
        var excludeIds = curated.Exclude.Keys.ToHashSet();
        var curatedIds = includeIds.Union(excludeIds).ToHashSet();

        var missing = foundIds.Except(curatedIds).OrderBy(x => x, StringComparer.Ordinal).ToList();
        var stale = curatedIds.Except(foundIds).OrderBy(x => x, StringComparer.Ordinal).ToList();
        var overlap = includeIds.Intersect(excludeIds).OrderBy(x => x, StringComparer.Ordinal).ToList();
        var errors = new List<string>();
        if (missing.Count > 0) errors.Add("uncurated CJK literals:\n  " + string.Join("\n  ", missing));
        if (stale.Count > 0) errors.Add("curated ids not present in dll:\n  " + string.Join("\n  ", stale));
        if (overlap.Count > 0) errors.Add("ids both included and excluded:\n  " + string.Join("\n  ", overlap));

        var byId = found.ToDictionary(f => f.Id, f => f.Zh);
        foreach (var (id, inc) in curated.Include)
            if (byId.TryGetValue(id, out var zh) && zh != inc.Zh)
                errors.Add($"zh mismatch for {id}: dll={Q(zh)} curated={Q(inc.Zh)}");
        foreach (var (id, reason) in curated.Exclude)
            if (string.IsNullOrWhiteSpace(reason))
                errors.Add($"exclude entry without reason: {id}");
        if (errors.Count > 0) throw new InvalidDataException(string.Join("\n", errors));

        var output = curated.Include
            .OrderBy(kv => kv.Key, StringComparer.Ordinal)
            .Select(kv => new Entry { Id = kv.Key, Zh = kv.Value.Zh, En = kv.Value.En, Note = kv.Value.Note })
            .ToList();
        WriteJson(a["out"], output);
        Console.WriteLine($"dump: {found.Count} CJK ldstr literals, {output.Count} included, {curated.Exclude.Count} excluded -> {a["out"]}");
        return 0;
    }

    // ---------------- patch ----------------

    private static int Patch(string[] args)
    {
        var a = ParseArgs(args, "dll", "map", "out");
        string stringsPath = a.GetValueOrDefault("strings") ?? "locales/dll_strings.json";
        var map = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(a["map"]), JsonOpts)
                  ?? throw new InvalidDataException("empty map");
        if (map.Count == 0) throw new InvalidDataException("map is empty");
        var canon = JsonSerializer.Deserialize<List<Entry>>(File.ReadAllText(stringsPath), JsonOpts)
                    ?? throw new InvalidDataException("empty strings file");
        var zhById = canon.ToDictionary(e => e.Id, e => e.Zh);

        foreach (var id in map.Keys)
            if (!zhById.ContainsKey(id))
                throw new InvalidDataException($"map id not in {stringsPath}: {id}");

        string dll = Path.GetFullPath(a["dll"]);
        string outPath = Path.GetFullPath(a["out"]);
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(Path.GetDirectoryName(dll)!);
        using var asm = AssemblyDefinition.ReadAssembly(dll, new ReaderParameters
        {
            AssemblyResolver = resolver,
            InMemory = true,
            ReadSymbols = false,
        });

        var patched = new HashSet<string>(StringComparer.Ordinal);
        foreach (var type in AllTypes(asm.MainModule.Types))
        {
            foreach (var method in type.Methods)
            {
                if (!method.HasBody) continue;
                int n = 0;
                foreach (var ins in method.Body.Instructions)
                {
                    if (ins.OpCode.Code != Code.Ldstr) continue;
                    string id = $"{type.FullName}::{method.Name}#{n}";
                    n++;
                    if (!map.TryGetValue(id, out var ko)) continue;
                    string zh = zhById[id];
                    if (ins.Operand is not string current)
                        throw new InvalidDataException($"{id}: operand is not a string");
                    if (current != zh)
                        throw new InvalidDataException($"{id}: current literal {Q(current)} != expected {Q(zh)}");
                    if (string.IsNullOrEmpty(ko))
                        throw new InvalidDataException($"{id}: empty replacement");
                    ins.Operand = ko;
                    patched.Add(id);
                }
            }
        }

        var unpatched = map.Keys.Except(patched).OrderBy(x => x, StringComparer.Ordinal).ToList();
        if (unpatched.Count > 0)
            throw new InvalidDataException("ids not found in assembly:\n  " + string.Join("\n  ", unpatched));

        Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
        asm.Write(outPath);
        Console.WriteLine($"patch: {patched.Count} ldstr operands rewritten -> {outPath}");
        return 0;
    }

    // ---------------- helpers ----------------

    private static List<(string Id, string Zh)> Scan(string path)
    {
        string dll = Path.GetFullPath(path);
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(Path.GetDirectoryName(dll)!);
        using var asm = AssemblyDefinition.ReadAssembly(dll, new ReaderParameters
        {
            AssemblyResolver = resolver,
            InMemory = true,
            ReadSymbols = false,
        });

        var list = new List<(string, string)>();
        foreach (var type in AllTypes(asm.MainModule.Types))
        {
            foreach (var method in type.Methods)
            {
                if (!method.HasBody) continue;
                int n = 0;
                foreach (var ins in method.Body.Instructions)
                {
                    if (ins.OpCode.Code != Code.Ldstr) continue;
                    string id = $"{type.FullName}::{method.Name}#{n}";
                    n++;
                    if (ins.Operand is string s && HasCjk(s)) list.Add((id, s));
                }
            }
        }
        return list;
    }

    private static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> types)
    {
        foreach (var t in types)
        {
            yield return t;
            foreach (var nested in AllTypes(t.NestedTypes)) yield return nested;
        }
    }

    private static bool HasCjk(string s)
    {
        foreach (char c in s)
            if (c is >= '\u2e80' and <= '\u9fff' or >= '\uff00' and <= '\uffef')
                return true;
        return false;
    }

    private static Dictionary<string, string> ParseArgs(string[] args, params string[] required)
    {
        var d = new Dictionary<string, string>(StringComparer.Ordinal);
        for (int i = 0; i < args.Length; i++)
        {
            if (!args[i].StartsWith("--")) continue;
            string key = args[i][2..];
            if (i + 1 < args.Length && !args[i + 1].StartsWith("--")) d[key] = args[++i];
            else d[key] = "true";
        }
        foreach (var r in required)
            if (!d.ContainsKey(r)) throw new ArgumentException($"missing --{r}");
        return d;
    }

    private static void WriteJson<T>(string path, T value)
    {
        var dir = Path.GetDirectoryName(Path.GetFullPath(path));
        if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
        File.WriteAllText(path, JsonSerializer.Serialize(value, JsonOpts) + "\n", new UTF8Encoding(false));
    }

    private static string Q(string s) => JsonSerializer.Serialize(s, JsonOpts);

    private sealed class Curated
    {
        [JsonPropertyName("include")] public Dictionary<string, IncludeEntry> Include { get; set; } = new();
        [JsonPropertyName("exclude")] public Dictionary<string, string> Exclude { get; set; } = new();
    }

    private sealed class IncludeEntry
    {
        [JsonPropertyName("zh")] public string Zh { get; set; } = "";
        [JsonPropertyName("en")] public string? En { get; set; }
        [JsonPropertyName("note")] public string Note { get; set; } = "";
    }

    private sealed class Entry
    {
        [JsonPropertyName("id")] public string Id { get; set; } = "";
        [JsonPropertyName("zh")] public string Zh { get; set; } = "";
        [JsonPropertyName("en")] public string? En { get; set; }
        [JsonPropertyName("note")] public string? Note { get; set; }
    }
}
