## Datapoke

What? You create YAML and JSON files using templates?  Seriously?

* Loops in a template just feels like the wrong tool for the job
* Getting indentation right is a real pain

And what about updates?

Suppose you want to create this YAML file:

```
    services:
      web:
        port: 80
        enabled: true
      api:
        port: 8080
        enabled: false
      db:
        port: 5432
        enabled: true
```

YAMLPath and JSONPath are standard ways to represent paths in YAML and JSON files.   The `list` subcommand lists all the paths so you don't have to figure it out yourself.

```
$ yamlpoke list foo.yaml
services.web.port: 80
services.web.enabled: true
services.api.port: 8080
services.api.enabled: false
services.db.port: 5432
services.db.enabled: true
services."the winner".port: 5432
services."the winner".enabled: true
```

See how "services.web.port" is a path representation of the "services: web: port: 80" line in the YAML file?

What if you could create your YAML and JSON files declaratively?

```
cat /dev/null > foo.yaml       # creates an empty file
yamlpoke poke services.web.port 80       foo.yaml
yamlpoke poke services.web.enabled true  foo.yaml
yamlpoke poke services.api.port 8080     foo.yaml
yamlpoke poke services.api.enabled false foo.yaml
yamlpoke poke services.db.port 5432      foo.yaml
yamlpoke poke services.db.enabled true   foo.yaml
```

And here's the result!

```
$ cat foo.yaml
services:
  web:
    port: 80
    enabled: true
  api:
    port: 8080
    enabled: false
  db:
    port: 5432
    enabled: true
```

You can do updates easily too!  Suppose you want to enable the api service? That's easy!  Just poke the value into place:

```
$ yamlpoke poke foo.yaml services.api.enabled true
```

And here's the result!

```
$ cat foo.yaml
services:
  web:
    port: 80
    enabled: true
  api:
    port: 8080
    enabled: true
  db:
    port: 5432
    enabled: true
```

But wait, what if you want to disable all the services?  Use `update` with a wildcard:

```
$ yamlpoke update foo.yaml 'services.*.enabled' false
```

And here's the result!

```
$ cat foo.yaml
services:
  web:
    port: 80
    enabled: false
  api:
    port: 8080
    enabled: false
  db:
    port: 5432
    enabled: false
```

There's also `jsonpoke` which does the same thing but for JSON files.

## What's next?

I should probably add a batch mode that accepts a list of paths, values, wildcards, etc. Instead of a template file, you could have a file of declarations that get applied to an empty file.

Then you could use templates to build the declarations file. (just kidding)