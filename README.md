# YandexStealData --- Technical Malware Analysis Report

> **Purpose:** Defensive reverse-engineering and incident-response
> documentation of the supplied Python source code.\
> **Scope:** This document describes behavior that is directly
> observable in the provided source files. It does not add, improve, or
> prescribe credential-theft, evasion, persistence, or exploitation
> capabilities.

------------------------------------------------------------------------

## 1. Executive Summary

`YandexStealData` is a Python script that targets locally stored
credential data belonging to Yandex Browser on Windows.

The supplied implementation:

1.  Resolves the Yandex Browser user-data directory under
    `%LOCALAPPDATA%`.
2.  Checks for the presence of the Yandex user-data directory.
3.  Terminates running `yandex.exe` processes.
4.  Reads the browser's `Local State` file.
5.  Obtains encrypted key material from the `os_crypt.encrypted_key`
    field.
6.  Uses Windows DPAPI to process that encrypted key material.
7.  Inspects Yandex Browser profile databases named `Ya Passman Data`.
8.  Reads `local_encryptor_data` from the profile database.
9.  Performs AES-GCM processing on the stored blob and derives a 32-byte
    master key.
10. Opens the `logins` table and reads stored login fields.
11. Computes a SHA-1-derived value from selected login metadata and uses
    it as additional authenticated data.
12. Processes the stored password blob with AES-GCM.
13. Prints recovered login information and appends it to
    `Yandex Passwords.txt`.

The important security observation is that the code is not merely
enumerating browser files: it contains a complete local
credential-recovery workflow, including browser key handling, database
access, authenticated decryption, and writing recovered credentials to a
local output file.

------------------------------------------------------------------------

## 2. Analysis Scope

### Source files reviewed

  -----------------------------------------------------------------------
  File                                Role
  ----------------------------------- -----------------------------------
  `yandex_browser_data.py`            Main data-extraction workflow

  `get_master_key_yandex.py`          Yandex key-handling and AES-GCM
                                      helper functions
  -----------------------------------------------------------------------

The analysis is based on the supplied source code only.

------------------------------------------------------------------------

# 3. Workflow Diagram

The following Mermaid diagram can be rendered by GitHub, GitLab, and
other Markdown platforms that support Mermaid.

``` mermaid
flowchart TD
    A["YandexStealData.py<br/>Python Script"] --> B["Program Entry Point<br/>__main__"]

    B --> C["Resolve Yandex User Data Directory<br/>%LOCALAPPDATA%/Yandex/YandexBrowser/User Data"]
    C --> D{"User Data Directory Exists?"}

    D -- "No" --> E["Print path-not-found message<br/>Exit"]
    D -- "Yes" --> F["Initialize YandexStealData"]

    F --> G["Locate Local State"]
    G --> H["Terminate running yandex.exe processes"]

    G --> I["Read Local State"]
    I --> J["Parse os_crypt.encrypted_key<br/>Base64 decoding"]

    J --> K["Windows DPAPI Processing<br/>CryptUnprotectData"]

    K --> L["Inspect Yandex Browser Profiles"]
    L --> M["Open each profile's<br/>Ya Passman Data SQLite database"]

    M --> N["Read local_encryptor_data<br/>from meta table"]

    N --> O["Process v10-encrypted blob<br/>AES-GCM"]
    O --> P["Validate Yandex-specific prefix"]
    P --> Q["32-byte master key obtained"]

    Q --> R["Open Ya Passman Data"]
    R --> S["Query logins table"]
    S --> T["Read URL / username / password fields"]

    T --> U["Build authentication metadata<br/>SHA-1 derived value"]

    U --> V["Process stored password blob<br/>AES-GCM"]

    V --> W["Recovered login record"]
    W --> X["Console output"]
    W --> Y["Yandex Passwords.txt"]

    H -. "Observed behavior" .-> Z["Detection / Monitoring<br/>Process termination"]
    I -. "Observed behavior" .-> Z2["Local browser data access"]
    K -. "Observed behavior" .-> Z3["DPAPI usage"]
    M -. "Observed behavior" .-> Z4["SQLite credential-store access"]
    Y -. "Artifact" .-> Z5["Credential dump written locally"]
```

------------------------------------------------------------------------

# 4. High-Level Architecture

The code can be divided into two logical components.

### Component A --- Main extraction workflow

`yandex_browser_data.py` contains the orchestration logic:

-   Browser-process handling
-   Profile enumeration
-   SQLite access
-   Login-table querying
-   Password processing
-   Output formatting
-   File writing

### Component B --- Key and cryptographic helper logic

`get_master_key_yandex.py` contains:

-   DPAPI wrapper
-   AES-GCM helper
-   `Local State` parsing
-   Encrypted browser-key handling
-   `Ya Passman Data` access
-   Master-key derivation/return

This separation is important for analysis because the main script
delegates key handling to the helper module.

------------------------------------------------------------------------

# 5. Detailed Execution Flow

## 5.1 Program entry

The main file executes the workflow from its `__main__` block.

The script constructs the Yandex Browser user-data path using the
Windows `LOCALAPPDATA` environment variable.

Observed source behavior:

-   Reads `LOCALAPPDATA`
-   Appends `Yandex\YandexBrowser\User Data`
-   Checks whether that directory exists
-   Terminates execution if it does not exist
-   Instantiates `YandexStealData` when it does

**Evidence:** `yandex_browser_data.py`, lines 102--108.

------------------------------------------------------------------------

## 5.2 Browser process termination

During initialization, the script calls `kill_yandex()`.

The function enumerates running processes through `psutil` and checks
process names for `yandex.exe`.

If a matching process is found, the process is terminated.

This behavior is relevant to defenders because it creates a directly
observable process event and may also be associated with access to
browser files that are otherwise locked.

**Evidence:** `yandex_browser_data.py`, lines 48--51.

### Security significance

Observed behavior:

``` text
Process enumeration
       ↓
Identify yandex.exe
       ↓
Terminate matching process
       ↓
Continue accessing browser data
```

No separate persistence mechanism is visible in the supplied code.

------------------------------------------------------------------------

# 6. Yandex Browser Key Handling

## 6.1 Reading Local State

The helper function reads the Yandex Browser `Local State` file.

The file is parsed as JSON and the following logical field is accessed:

``` text
os_crypt.encrypted_key
```

The value is Base64-decoded before further processing.

**Evidence:** `get_master_key_yandex.py`, lines 31--46.

------------------------------------------------------------------------

## 6.2 Windows DPAPI

After Base64 decoding, the code removes the browser-specific prefix from
the resulting byte sequence and passes the remaining material to:

``` text
win32crypt.CryptUnprotectData(...)
```

This represents Windows DPAPI-based unprotection of locally protected
key material.

**Evidence:** `get_master_key_yandex.py`, lines 22--29 and 41--46.

### Defensive significance

DPAPI access is a useful telemetry point because legitimate applications
also use it, but its combination with:

-   browser credential-store access,
-   SQLite database access,
-   AES-GCM processing, and
-   credential output

creates a much stronger behavioral signal than any one event alone.

------------------------------------------------------------------------

# 7. Profile Enumeration

The helper contains a fixed list of browser profile names:

``` text
Default
Profile 1
Profile 2
Profile 3
Profile 4
Profile 5
Person 1
Person 2
Person 3
```

For each profile, the code constructs a path to:

``` text
Ya Passman Data
```

and skips profiles for which the database does not exist.

**Evidence:** `yandex_browser_data.py`, lines 27--46;
`get_master_key_yandex.py`, lines 52--67.

------------------------------------------------------------------------

# 8. Master-Key Derivation Workflow

For each available profile database, the helper opens the SQLite
database and queries the `meta` table for:

``` text
local_encryptor_data
```

**Evidence:** `get_master_key_yandex.py`, lines 71--78.

The resulting encrypted blob is then processed as an AES-GCM encrypted
structure.

The implementation:

1.  Searches for a `v10` marker.
2.  Extracts the corresponding encrypted portion.
3.  Treats the first 12 bytes as an IV.
4.  Processes the remaining encrypted material with AES-GCM.
5.  Checks for the expected Yandex-specific prefix.
6.  Returns the following 32-byte segment as the master key.

**Evidence:** `get_master_key_yandex.py`, lines 84--91.

### Important reporting note

The actual secret/prefix value should not be reproduced in a public
report. A safe representation is:

``` text
[Yandex-specific validation prefix — redacted]
```

------------------------------------------------------------------------

# 9. Credential Database Access

After the master key is available, `YandexStealData.extract_data_()`
processes the profile's `Ya Passman Data` database.

The code opens the database with SQLite.

It queries the `logins` table for:

-   `origin_url`
-   `username_element`
-   `username_value`
-   `password_element`
-   `password_value`
-   `signon_realm`

**Evidence:** `yandex_browser_data.py`, lines 68--75.

This establishes that the implementation specifically targets stored
browser login records.

------------------------------------------------------------------------

# 10. Password Decryption Workflow

For every login row, the script constructs a string from selected login
metadata:

``` text
origin_url
username_element
username_value
password_element
signon_realm
```

The fields are joined using null-byte separators.

The resulting value is SHA-1 hashed.

The digest is then passed to the AES-GCM helper as additional
authenticated data.

**Evidence:** `yandex_browser_data.py`, lines 76--78 and 84--89.

The stored `password_value` is split into:

``` text
IV
Encrypted password + authentication tag
```

The AES-GCM helper:

-   extracts the final 16 bytes as the authentication tag,
-   creates an AES-GCM cipher,
-   optionally supplies the calculated authentication data,
-   decrypts and verifies the ciphertext.

**Evidence:** `yandex_browser_data.py`, lines 80--89;
`get_master_key_yandex.py`, lines 13--20.

------------------------------------------------------------------------

# 11. Recovered Data

When the decryption operation produces a non-empty result, the script
formats a record containing:

-   Browser profile
-   Origin URL
-   Username
-   Decrypted password

The result is displayed in the console.

**Evidence:** `yandex_browser_data.py`, lines 90--92.

### Sensitive-data handling

A report should use placeholders such as:

``` text
URL: [REDACTED]
Username: [REDACTED]
Password: [REDACTED]
```

Do not include real credentials in screenshots, logs, Git commits, or
incident tickets.

------------------------------------------------------------------------

# 12. Output Artifact

The script appends the formatted credential records to:

``` text
Yandex Passwords.txt
```

The file is opened in append mode with UTF-8 encoding.

**Evidence:** `yandex_browser_data.py`, lines 91--94.

This is a concrete forensic artifact.

### Recommended evidence collection

For an authorized investigation, defenders should record:

-   File creation/modification timestamps
-   File size
-   File hash
-   Parent process
-   Process command line
-   File-system events around the execution time
-   Associated Python interpreter activity
-   Process termination events involving `yandex.exe`

------------------------------------------------------------------------

# 13. Observed Detection / Monitoring Opportunities

The supplied implementation contains several behaviors that defenders
can monitor.

## High-value behavioral signals

### 1. Unexpected termination of Yandex Browser

The script explicitly searches for and terminates `yandex.exe`.

**Source:** `yandex_browser_data.py`, lines 48--51.

### 2. Access to browser Local State

The helper reads the browser's `Local State` file and accesses encrypted
key metadata.

**Source:** `get_master_key_yandex.py`, lines 31--46.

### 3. DPAPI access

The script invokes Windows DPAPI through `CryptUnprotectData`.

**Source:** `get_master_key_yandex.py`, lines 22--29 and 46.

### 4. Access to `Ya Passman Data`

The script accesses profile-level SQLite databases containing browser
credential data.

**Source:** `get_master_key_yandex.py`, lines 64--76.

### 5. Access to the `logins` table

The main extractor explicitly queries login-related columns.

**Source:** `yandex_browser_data.py`, lines 68--75.

### 6. Creation/modification of `Yandex Passwords.txt`

The script writes recovered data to a local text file.

**Source:** `yandex_browser_data.py`, lines 91--97.

------------------------------------------------------------------------

# 14. Detection Chain

A useful defensive detection model is:

``` text
Unexpected Python execution
        │
        ▼
Access to Yandex Browser data
        │
        ▼
yandex.exe termination
        │
        ▼
Local State access
        │
        ▼
DPAPI operation
        │
        ▼
Ya Passman Data SQLite access
        │
        ▼
Login-table access
        │
        ▼
Cryptographic processing
        │
        ▼
Credential-like data written to a text file
```

A single event may be legitimate.

The combination and ordering of these events is significantly more
suspicious and should be prioritized for investigation.

------------------------------------------------------------------------

# 15. MITRE ATT&CK Mapping

The mapping below should be treated as a reporting aid rather than proof
of a specific ATT&CK technique.

  -----------------------------------------------------------------------
  Technique               Assessment              Reason
  ----------------------- ----------------------- -----------------------
  **T1555 -- Credentials  Strongly supported      The code accesses
  from Password Stores**                          browser-stored login
                                                  records and processes
                                                  stored password values.

  **T1555.003 --          Strongly supported      The implementation
  Credentials from Web                            specifically targets
  Browsers**                                      Yandex Browser
                                                  credential storage.

  **T1005 -- Data from    Supported               The script reads local
  Local System**                                  browser files and
                                                  databases.

  **T1070 / Defense       Do not automatically    Process termination is
  Evasion**               assign                  observed, but the
                                                  supplied code alone is
                                                  insufficient to
                                                  establish a broader
                                                  ATT&CK defense-evasion
                                                  objective.

  **Ingress Tool          Not observed            No download mechanism
  Transfer**                                      is present in the
                                                  supplied files.

  **Exfiltration Over Web Not observed            No network transmission
  Service**                                       mechanism is present in
                                                  the supplied files.

  **Persistence**         Not observed            No startup, scheduled
                                                  task, service, registry
                                                  persistence, or
                                                  equivalent mechanism is
                                                  visible.

  **Anti-debug /          Not observed            No explicit
  Anti-analysis**                                 anti-debugging or
                                                  anti-analysis logic is
                                                  present in the supplied
                                                  files.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 16. Evidence Mapping

  ---------------------------------------------------------------------------------------------------------
  Diagram Element     Source                          Code Reference Observed Behavior        Confidence
  ------------------- ---------------------------- ----------------- ------------------------ -------------
  Initial execution   `yandex_browser_data.py`              102--108 Resolves Yandex User     High
                                                                     Data and initializes     
                                                                     extractor                

  Process termination `yandex_browser_data.py`                48--51 Enumerates processes and High
                                                                     terminates `yandex.exe`  

  Local State access  `get_master_key_yandex.py`              31--46 Reads and parses         High
                                                                     encrypted browser-key    
                                                                     metadata                 

  DPAPI               `get_master_key_yandex.py`          22--29, 46 Uses Windows DPAPI       High
                                                                     unprotection             

  Profile discovery   Both files                     27--46 / 52--67 Enumerates Yandex        High
                                                                     profiles                 

  `Ya Passman Data`   `get_master_key_yandex.py`              64--76 Opens profile SQLite DB  High
  access                                                             and reads encryption     
                                                                     metadata                 

  Master-key          `get_master_key_yandex.py`              84--91 AES-GCM processing and   High
  processing                                                         32-byte key extraction   

  Login DB access     `yandex_browser_data.py`                68--75 Queries `logins` table   High

  Authentication data `yandex_browser_data.py`                76--78 Computes SHA-1-derived   High
                                                                     metadata                 

  Password processing `yandex_browser_data.py`                80--89 AES-GCM decrypt/verify   High
                                                                     operation                

  Recovered record    `yandex_browser_data.py`                90--92 Formats URL, username    High
                                                                     and password             

  Output artifact     `yandex_browser_data.py`                91--97 Writes results to        High
                                                                     `Yandex Passwords.txt`   
  ---------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 17. Forensic Artifacts

The following artifacts are directly relevant to an investigation:

``` text
YandexStealData.py
get_master_key_yandex.py
Yandex Browser User Data/
    Local State
    <Profile>/
        Ya Passman Data
Yandex Passwords.txt
```

Potential host telemetry:

``` text
python.exe / python interpreter activity
yandex.exe process termination
File reads against Yandex Browser directories
SQLite database access
DPAPI API activity
Creation/modification of Yandex Passwords.txt
```

------------------------------------------------------------------------

# 18. What Is NOT Observed

The supplied source does **not** show evidence of:

-   Network-based credential exfiltration
-   HTTP/HTTPS command-and-control
-   Discord/Telegram webhook transmission
-   Persistence
-   Scheduled tasks
-   Registry Run keys
-   Service installation
-   Process injection
-   Remote process creation
-   Credential collection from unrelated browsers
-   Anti-debugging
-   Virtual-machine detection
-   Explicit security-product detection
-   Self-deletion

These statements are limited to the supplied files and should not be
generalized to components that were not provided.

------------------------------------------------------------------------

# 19. Analyst Notes and Limitations

### Source-only limitation

This report analyzes source code, not a complete runtime sample.

Runtime behavior may differ if:

-   another module is loaded dynamically,
-   configuration is supplied externally,
-   environment variables affect execution,
-   a parent process performs additional actions,
-   the supplied files are only part of a larger project.

### No network behavior confirmed

The supplied files do not contain a network transmission stage.

Therefore, the local output file should be considered the observed
terminal output of this code path rather than evidence of successful
remote exfiltration.

### No persistence confirmed

There is no persistence mechanism in the reviewed files.

### Secrets intentionally redacted

Any hard-coded cryptographic material, credentials, or recovered values
should be redacted from public documentation.

------------------------------------------------------------------------

# 20. Recommended Defensive Controls

For defenders investigating this behavior:

1.  Alert on unusual Python processes accessing browser credential
    stores.
2.  Correlate `yandex.exe` termination with subsequent access to Yandex
    Browser profile databases.
3.  Monitor access to `Local State` and `Ya Passman Data` by unexpected
    processes.
4.  Monitor DPAPI use in suspicious process contexts.
5.  Alert on creation of credential-dump-like text files.
6.  Preserve process, file-system, and Windows security telemetry around
    the event.
7.  Rotate credentials that may have been exposed.
8.  Review other browser profiles and user accounts if the same
    execution context had access to them.
9.  Preserve the original sample and compute cryptographic hashes before
    analysis.
10. Perform analysis in an isolated, authorized environment.

------------------------------------------------------------------------

# 21. Analyst Summary

**Observed objective:** Local recovery of saved Yandex Browser
credentials.

**Primary data source:** Yandex Browser profile `Ya Passman Data` SQLite
databases.

**Key-handling components:** Yandex `Local State`, Windows DPAPI, and
AES-GCM processing.

**Credential source:** `logins` table.

**Observed output:** `Yandex Passwords.txt`.

**Observed network exfiltration:** None in the supplied files.

**Observed persistence:** None in the supplied files.

**Observed anti-analysis:** None in the supplied files.

**Most significant detection opportunity:** Correlating browser-process
termination, browser credential-store access, DPAPI activity, SQLite
access, and credential-like file creation within the same execution
chain.

------------------------------------------------------------------------

## 22. Source References

### `yandex_browser_data.py`

-   Main entry point and Yandex User Data path: lines 102--108
-   Browser process termination: lines 48--51
-   Profile enumeration: lines 27--46
-   Login database query: lines 68--75
-   Authentication-data construction: lines 76--78
-   Password processing: lines 80--89
-   Credential formatting/output: lines 90--97

### `get_master_key_yandex.py`

-   AES-GCM helper: lines 13--20
-   DPAPI helper: lines 22--29
-   Local State parsing: lines 31--46
-   Profile database access: lines 52--76
-   Master-key processing: lines 84--91

------------------------------------------------------------------------

## Disclaimer

This document is intended for authorized malware analysis, incident
response, detection engineering, and security research. It documents the
behavior present in the supplied source and intentionally avoids
providing additional credential-theft or evasion functionality.
