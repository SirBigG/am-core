# Контракт сутностей, зв’язків і конфігурованих блоків

- Дата: 2026-11-15.
- Статус: **Accepted, 2026-11-16**. Користувач прийняв контракт AGRO-73 після незалежної перевірки AC-1–AC-5. SHA-256 перевіреної редакції: `d3da6a5d56f917dfaa1fff21e757ad8281152faf94674948231274b29e309704`.
- Owning application: `am-core`; запропонований Django app `core.catalog`, у тій самій БД. Нового сервісу немає.
- Задачі: [AGRO-73](http://localhost:8090/roar/projects/0f4660b9-fa20-4bc4-b738-1715493b6747/issues/66580398-9990-41c8-a5cd-c95a29fdf54d), parent AGRO-72; предметне розширення AGRO-85.
- Пріоритет правил: [погоджений контракт AGRO-2](2026-10-23-core-sites-content-language-contract.md). Погодження AGRO-2 не означає погодження цього нового дизайну.

## 1. Джерела істини й поточна поведінка

AGRO-2 визначає одну ідентичність CatalogEntity, спільний PostText(post, locale), pending revisions і SitePostPublication. Цей контракт їх використовує. Окремих RelationEntity, локальних body overrides або власної мовної сертифікації не створюємо.

Погоджений ADR AGRO-2 відсутній у початковому checkout `169bad448ce2f4ea73b97998fcbaf6aa2007e498`, але існує в Git-об’єкті `101b68425c99d826a6ebc64567d80630896924ef:docs/engineering/decisions/2026-10-23-core-sites-content-language-contract.md`. Його SHA-256 `d330e043fce94d45115cacc8e3ddb4a602d7a8adf5071f54d3eb8d6b27cf0365` точно збігається з актуальним посиланням у Plane. Документ відновлено байт у байт, без cherry-pick коду або зміни старого ADR про міжнародну платформу. Це усуває прогалину джерела, але не доводить реалізацію AGRO-2/4/5/7/9/10.

| Owning source | Що існує | Чого це не забезпечує |
| --- | --- | --- |
| `core/posts/models.py`: Post, GuideSection, GuideSectionArticle | Post PK, title/body/status/date/rubric/URL; впорядковані посилання на статті | Entity/text/publication split і типізовані застосування не реалізовані; guide placement не є підтвердженням застосування |
| `core/classifier/models.py`: Category, CategoryHub, CategoryHubSection | MPTT, глобальний slug, presentation, site/locale hub config, категорійні секції | Категорія навігації не є автоматично біологічною ідентичністю; current OneToOne hub не є майбутнім multi-site контрактом |
| `core/companies/models.py`: Product; `core/registry/models.py`: Variety | Product.post, match status/source keys/prices; Variety.publication | Post PK зараз використовується ринком; title, речовина чи номер заявки не є глобальним entity key |
| `api/v1/content/{views,hubs,management}.py` | Token API, staff/model/own-post permissions, транзакції, Admin audit | Немає relation lifecycle, If-Match, domain review чи role-scoped publication service |
| `core/posts/{crop_hub,guide_hub}.py` | Активність, дата, активні предки, canonical, scoped config | Site/locale cache namespace не доводить membership Post або мову тексту |
| `core/search/models.py`, `core/companies/market.py` | Індекс generation/type/source; окремі правила цін і пропозицій | Немає повної site/locale publication isolation; ринковий eligibility не є regulatory eligibility |

Це source inspection, без нового аудиту production або локальних бізнес-даних. Відомий legacy дефект прямого detail для status=false не ремонтуємо тут; нові relation readers завжди виключають непублічних учасників.

## 2. Єдина ідентичність і прив’язка джерел

`CatalogEntity(id UUID, kind, state, provenance, created_by, created_at, version)` — одна модель, спільна для AGRO-4/74. UUID opaque й незмінний; `kind` з контрольованого реєстру: crop, cultivar, disease, pest, weed, preparation. Нові kind проходять schema review. Назва, мова, URL і category slug не входять до UUID. Стан active/archived контролює використання, а не публікацію тексту.

AGRO-4 володіє введенням цієї моделі й nullable `Post.entity` з FK PROTECT. AGRO-74 залежить саме від цього additive entity/mapping deliverable, а не від повної реалізації всього multisite feature. Якщо AGRO-4 ще не готова, AGRO-74 не створює альтернативну модель; перенесення ownership потребує явного погодженого scope change.

Для crop AGRO-74 додає nullable `Category.entity` з FK PROTECT і перевіркою kind=crop. Hub отримує crop через свою Category. Категорія не зобов’язана мати Post. Кілька навігаційних категорій можуть явно посилатися на ту саму crop; canonical category визначає scoped resolver, а не випадкова `.first()`. Mapping створює уповноважений редактор із provenance, не евристика назви чи дерева.

Post.entity дозволяє кілька незалежних матеріалів про одну сутність. Для кожного site/locale public resolver вибирає **явно призначений** canonical material/publication для entity; publication має належати цьому entity. Якщо вибору немає або він неоднозначний, картка не видається. Жодного вибору за мінімальним PK, UI language або схожістю заголовків. Mapping canonical material зберігає AGRO-4 publication adapter, AGRO-74 його споживає.

Для цього AGRO-74 визначає `EntityPresentationSelection(site, content_locale, entity, post?, category?)`: UNIQUE(site, content_locale, entity), рівно один із post/category, обидва FK PROTECT. Post.entity/Category.entity мають збігатися з entity; category дозволена тільки для crop. Це явний вибір джерела картки, а не нова entity/text/publication модель. AGRO-4/5 adapters розв’язують вибраний Post/Category у чинну publication/config; таблиця не зберігає копій body або canonical URL. Без approved selection та відповідної доступної publication картка не будується. Зміна selection — scoped publication action із If-Match та audit, не побічний ефект звичайного body edit. Вибір legacy und дозволений тільки за винятком AGRO-2, без підміни content_locale мовою UI.

Variety.publication і Product.post не переприв’язуються; новий entity layer не замінює ці FK. Наявність Variety.publication не доводить registry/entity equivalence без перевіреного mapping. AGRO-9 володіє цим адаптером; registry row без Post не породжує матеріал. Seller Product — пропозиція, а preparation entity — конкретний препарат/формуляція. Продукти продавців та схожі діючі речовини не стають учасниками застосування автоматично.

## 3. Спільна схема зв’язків

Усі моделі нижче — запропонований storage contract для AGRO-74; моделі AGRO-4 не дублюються.

| Модель | Контракт |
| --- | --- |
| RelationTypeVersion | Незмінні code/schema_version, ролі, допустимі entity kinds, min/max, direction/symmetry, self/cycle policy, identity fields, payload validator. Схеми версіоновані в коді/міграціях, не виконуваний код із Admin |
| RelationRecord | UUID, type code, immutable semantic identity JSON+digest, lock_version, archived, withdrawn, eligibility_epoch, optional superseded_by FK PROTECT, actor/time. UNIQUE(type code, identity_digest), у тому числі для withdrawn/archived records |
| RelationRevision | UUID, record FK PROTECT, revision number, schema version FK PROTECT, immutable participants/payload/source snapshot і created_epoch, base approved revision, review state, approval_epoch/actor/time. UNIQUE(record, revision number); approved content і його approval не перестворюються на тому самому revision ID |
| RelationParticipant | revision FK, role code, ordinal, entity FK PROTECT. UNIQUE(revision, role, entity); UNIQUE(revision, role, ordinal). Прив’язка до конкретної revision, не mutable M2M поточного запису |
| RelationRelease | UNIQUE(site, record), approved_revision FK, enabled, lock_version; revision належить цьому record. Один live pointer на site; locale не копіює нейтральний факт |
| RelationAuditEvent | Append-only record/revision/action/actor/time/request ID/base version/result/source digest; доступ як до приватного редакційного журналу |
| RelationWithdrawal | Append-only UUID, record FK PROTECT, resulting eligibility_epoch, reason/source evidence, blocked source-version digests, actor/time, affected site IDs. Одна global дія для цього record; старі revisions не перевипускаються |
| SourceWithdrawalGate | UNIQUE(type code, country, canonical source-version digest), immutable blocked=true decision/evidence/actor/time. Забороняє позитивне використання відкликаної версії джерела в усіх records цього scope; нова версія джерела не успадковує review |
| RelationScopeGate | UNIQUE(type code, country), quarantined, lock_version, source-withdrawal reference/reconciliation evidence. Durable fail-closed перемикач, якщо affected scope джерела ще не повністю відомий; не очищується feature off/on |
| RelationIdentityCorrection | Append-only old/new record FK PROTECT, old/new full identity digests, reason/evidence, actor/time, withdrawal event FK. Старий record має не більше одного successor; self-links і cycles заборонені |
| ImportReceipt | UNIQUE(actor scope, operation key), canonical request digest, stable result/error references; повтор іншого payload під тим самим ключем — 409 |

Фізичні CHECK/FK/UNIQUE захищають локальні поля. Кратність, kind/role, належність revision до record/release, sealed revision і cross-row consistency перевіряє одна transactional service плюс deferred constraint triggers на commit. Тригери входять до AGRO-74, з direct SQL negative tests: лише Model.clean недостатньо. Не дозволяється частково заповнена sealed revision. Незавершений HTTP payload збирається й запечатується атомарно; немає проміжного публічного стану.

Правка полів поза semantic identity створює нову immutable revision; review transitions і releases не переписують її вміст. Редактор готує payload цілком; нове збереження чернетки створює наступну revision. Identity-changing correction виконується тільки через окремий перехід нижче. Попередні revisions залишаються в приватній історії за своїми ID; public доступ залежить від поточних release/withdrawal gates. Видалення історії через звичайний API/Admin не підтримується.

Semantic identity серіалізується канонічним JSON із versioned normalization, без title, display labels та source retrieval timestamps. Порівнюються повні identity bytes; hash collision дає конфлікт, а не merge. Type schema version не входить до унікальності logical record: міграція схеми не створює дублі факту. Для symmetric type учасники сортуються за UUID; directed ролі не переставляються. Конкурентний create покладається на DB unique, після конфлікту читає існуючий запис і звіряє повний ключ. Неперевірені дублікати не overwrite approved дані.

### Незмінність identity та correction path — VERIFY-01

Для **кожної** revision canonical identity projection її participants/payload має байт у байт дорівнювати immutable identity її record. Service і deferred DB guard перевіряють це при create/seal/approval; API revision update з іншою identity повертає 409 `identity_change_requires_correction`. Зміна preparation/crop/target/country/method/registration/application keys у application не може переписати ключ record або створити його revision під старим ключем. Preparation entity також не можна переозначити з однієї фактичної формуляції на іншу: потрібна нова перевірена entity. Versioned normalization/schema migration мусить зберігати цю projection; зміна identity semantics потребує окремого reviewed mapping/correction, не тихого rekey.

`correct-identity` отримує old record If-Match, повний corrected payload, reason/evidence і operation key. Це explicit safety correction, не звичайний import. За спільним lock type і sorted old/new record identity keys service атомарно: (1) знаходить або створює єдиний corrected-key record через DB UNIQUE і повне порівняння ключа; (2) створює там draft revision лише з explicit правами й актуальним If-Match існуючого target, або повертає scoped noop/reference без зміни його content; (3) виконує global withdrawal старого record, прив’язує `superseded_by` і append-only correction event. Будь-яка помилка/відсутні права/неоднозначність скасовує всю транзакцію. Якщо old і corrected identity однакові, correction відхиляється: потрібна non-identity revision.

Existing corrected-key record не дублюється й не auto-approve/release/reactivate; його approved revisions, withdrawal і site releases зберігають власні gates. Collision із прихованим target не розкриває його payload і дає scoped conflict. Звичайний batch import не може сам відкликати чи supersede record: він повертає correction-required conflict для explicit old-record correction. Незалежний імпорт corrected key без old-record reference все одно resolve-ить той самий target record за UNIQUE. Pending source clarification, яка не стверджує помилковість identity, створює звичайну revision і не відкликає live.

Correction негайно прибирає старий факт на всіх sites, навіть коли successor ще draft: хибний факт не лишається live до його заміни. Старі identity bytes, revisions, source citations і releases зберігаються в історії. Повтор operation key повертає той самий receipt; паралельний create corrected key resolve-иться в один target; stale old/target version — 409. Superseded record не можна reinstate/unarchive/release або supersede повторно іншим target звичайними actions. Reversal/merge такої correction — окремий maintenance scope. Всі correction edges перевіряються на cycles під type lock, у тому числі A→B проти B→A. Для `cultivar_of` crop не входить до його identity (ключ — cultivar), тому зміна crop є non-identity revision зі старими uniqueness/approval locks; жодного винятку для application identity це не створює.

### Два типи й один адаптер контексту

| Type | Ролі й кратність | Напрям, self-links, cycles | Identity |
| --- | --- | --- | --- |
| related_to/v1 | member: рівно 2 різні entity дозволених schema kinds | Symmetric; self заборонено; цикли графа дозволені; транзитивних висновків немає | Впорядкована пара UUID |
| plant_protection_application/v1 | preparation:1, crop:1, target:0..1; target kind disease/pest/weed; target_kind=other допускає лише вихідний текст | Role-directed гіперребро; self заборонено; цикли не мають сенсу через різні kind; немає успадкування чи транзитивності | preparation, crop, target UUID або нормалізований source target locator, country, method code, registration authority+record key, application locator |
| cultivar_of/v1 | cultivar:1, crop:1 | Directed; self заборонено; зворотна role несумісна з kind; schema не допускає ланцюжків cultivar→cultivar | cultivar UUID; одна чинна approved crop-прив’язка для cultivar, серіалізоване затвердження за cultivar |

`related_to` — навігаційний факт, ніколи не використовується як доказ реєстрації/ефективності. `cultivar_of` — явний зв’язок для контексту сорту AGRO-85; дерево рубрик його не замінює. Два конкуруючі crop assignments відхиляються на approval під одним lock cultivar; історія старих revisions зберігається.

Новий довільний тип із ациклічністю потребує окремого schema change: cycle test під спільним транзакційним lock для цього графа й рекурсивна перевірка, із concurrency test. Поточний контракт не обіцяє довільний executable graph engine.

### Архівація й видалення

Entity/record archive — явна audit дія. Record archive негайно блокує всі його releases, але не видаляє їх. Participant entity archive прибирає всі записи з public selection. Публікація material може бути знята на одному site без видалення entity, історії або інших site releases.

Archive і site-local unrelease не замінюють global withdrawal. Unarchive не очищує withdrawn/eligibility_epoch/superseded_by. Старі records не звільняють semantic unique key після archive/withdrawal, тому імпорт не може обійти відкликання створенням дубля того самого факту.

Історичні participant FK використовують PROTECT. Entity hard delete і type-version delete за наявності історії відхиляються. Видалення Post/Category, що є verified anchor/canonical material, через звичайний writer відхиляється до окремого reconciliation: не залишати relation, яка посилається на зниклу identity. Deactivation дозволена й одразу впливає на eligibility. Масове видалення/злиття — окремий maintenance scope, не cascade з relation editor. Адаптери AGRO-4/5/9 мають забезпечити ці правила у власних моделях.

## 4. AGRO-85: предметне розширення без другого рушія

`PlantProtectionApplicationDetails` — typed OneToOne extension **RelationRevision**, у тому самому `core.catalog`, без власних participants, revision system, releases, CRUD/import або renderer. AGRO-85 володіє полями/validator цього type, AGRO-74 — спільними механізмами. Ключі й schema seed AGRO-85 додає через контрольовану реєстрацію type.

Обов’язкові до approval: конкретний formulation identity/verification provenance; country (окремий від site/locale); method code із контрольованого словника; registration authority/record key; application locator; source URL/reference, документ/version/digest, checked_at і reviewer; valid_from/valid_until з відомими межами; точний target або unresolved source text; regulatory decision і її provenance. Картка препарату сама по собі не є доказом формуляції.

Unknown зберігається NULL/explicit unresolved state. Unknown validity не означає безстроковий дозвіл. Для публічного пілота потрібні відомі дати, підтверджена конкретна формуляція і regulatory decision=confirmed; approval редактора та regulatory eligibility — різні осі. `checked_at` не може бути в майбутньому. Дати документа inclusive у country calendar: local date D допустима від valid_from до valid_until включно; cache boundary — наступна local midnight після valid_until. Country timezone задає перевірена конфігурація, не timezone браузера. Unknown country/timezone — fail closed.

Групову ціль зберігаємо з target=NULL і target_kind/source text; вона не створює точних target links. Такий approved запис може бути видимим на препараті/культурі з буквальним описом цілі, але не в добірці конкретної хвороби/виду. Вибір точного target потребує нового source review. Ніякого поширення за речовиною, класом фунгіцидів, HTML-посиланням або спільною Guide-добіркою.

Різні method/application locator створюють різні records. Нова source version/validity/provenance при незмінній identity — нова revision цього record; UNIQUE(revision, source reference, version, application locator) у provenance extension запобігає дублю рядка всередині revision. Повторний import того самого source+payload повертає існуючу revision, але receipt не надає права повторно опублікувати withdrawn revision. Суперечливі джерела створюють pending conflict, не auto-approve і не auto-replace. Зміна фактичної формуляції/preparation або unresolved→exact target — identity correction, не revision старого ключа. Non-identity material source/validity edit не успадковує старий review. Якщо нове свідчення спростовує чинний дозвіл, обов’язкова global withdrawal дія з розділу 5, а не лише unrelease одного site; звичайне pending уточнення не переписує попередню перевірену revision.

Дози опціональні: min/max, unit code, спосіб/умови в цій revision; min≤max, одиниці перевіряються разом із методом. NULL не перетворюємо на 0. Пілот може не показувати доз узагалі. Перерахунків на присадибні ділянки, порад лікування й автоматичного agronomic approval немає.

Сорт отримує crop тільки через approved `cultivar_of`; підпис «Для культури …». Це не підтвердження ефективності на конкретному сорті. Одна підготовлена стаття може відображатися у кількох блоках з одним scoped canonical URL без копіювання Post.

## 5. Review, права та конкурентні зміни

Revision states: draft → submitted → approved або rejected; нова правка rejected/submitted створює draft revision. Approved content immutable. Release/unrelease і record archive — окремі audit дії, не редакторський статус body. Review не активує site release автоматично.

### Стійке відкликання й відновлення — VERIFY-02

Record створюється з withdrawn=false та eligibility_epoch=0. Кожна revision фіксує created_epoch, approval — той самий approval_epoch. Explicit `withdraw` — **global для record на всіх sites**: під record lock service збільшує eligibility_epoch, встановлює withdrawn=true, створює незмінний RelationWithdrawal з evidence/blocked source-version digests, вимикає всі releases і змінює їхні versions, атомарно пише generation/outbox для всіх affected sites. Не створюється жодної паузи, коли лише частина sites втратила доступ. Domain reviewer з explicit `withdraw_relation` capability в type/country scope може виконати це safety action для всього record; site publisher не може звузити його до одного site. Простий unrelease лишається локальною редакційною дією без regulatory значення.

Release та public selector обов’язково вимагають withdrawn=false, superseded_by=NULL і created_epoch=approval_epoch=current record eligibility_epoch. Тому всі revisions, які існували до withdrawal, назавжди втрачають release eligibility, навіть якщо їхній історичний status лишився approved або хтось unarchive-ив record. Стару revision не можна reapprove під новим epoch; old payload/receipt/PUT статусу цього не обходить. Deferred DB guards захищають epoch/withdrawal gate для release; selector перевіряє його синхронно до count/facets, незалежно від cache/worker. Approved payload не змінюється: відкликання зберігається окремо в життєвому циклі record.

Відновлення при **тій самій** identity: створити нову revision після withdrawal (created_epoch=current epoch) з новим перевіреним свідченням, яке явно розв’язує причину останнього withdrawal; blocked source-version digest не може бути позитивним доказом нового дозволу. Потрібні новий domain review і окремий `reinstate` action з If-Match record, withdrawal event ID та approved candidate revision ID цього epoch. Review сам не знімає withdrawn. Reinstate потребує explicit `reinstate_relation` capability разом із domain review; якщо заторкнуто кілька sites, додатково platform administrator за shared approval правилом AGRO-2. Для одного site потрібен його publisher. Жодних grants цим контрактом не призначено.

Reinstate повторно перевіряє identity, source evidence, current epoch і відсутність superseded_by; очищує тільки withdrawn flag, пише audit/generation і **залишає всі releases disabled**. Подальший publisher явно release-ить лише нову eligible approved revision. Archived record додатково потребує власної unarchive policy, яка не замінює reinstate. Нова withdrawal, поки candidate готується, знову збільшує epoch: candidate стає stale і потребує нової revision, не повторного approve старого ID. Якщо змінилась identity, потрібен correct-identity/new record, а не reinstate старого.

Withdrawal↔release/reinstate/approval серіалізуються одним record lock і lock_version: release, що завершився першим, буде вимкнений withdrawal; withdrawal, що завершилась першою, робить старий release/reinstate 409/неeligible. Після commit жодна fresh public вибірка старого epoch не повертається, навіть на другому site. Повтор того самого operation key — receipt, а не нове збільшення epoch. Один source withdrawal може стосуватися кількох records: action зобов’язаний явно перелічити перевірені affected record IDs і застосувати той самий gate для кожного; blanket invalidation довільного URL без source review не підтримується. Повне відкликання документа не можна завершити частково: усі відомі affected records блокуються атомарно, а майбутній import його blocked source-version digest відхиляється за shared withdrawal ledger у тому самому type/country scope. Якщо повний affected scope ще невідомий, відповідний type/country public feature тимчасово fail-closed до reconciliation; не заявляти завершений withdrawal за одним випадковим record.

Source-level withdrawal створює `SourceWithdrawalGate` і за потреби встановлює `RelationScopeGate.quarantined=true` в тій самій транзакції, під type/scope lock до record locks. Сам digest відображає канонічну source identity+version+content digest, не довільний URL; усі source references нормалізуються до нього. Create/import/review/release і public selector перевіряють обидва gates. Для незавершеного scope reconciliation domain reviewer із `withdraw_relation` та platform administrator можуть лише зняти quarantine після перевірки повного affected manifest і нового If-Match; blocked source-version gate не видаляється й старий epoch не повертається. Source ledger/records/generation — одна транзакція; паралельний import, що встиг раніше, входить до повторного affected lookup під тим самим lock, а пізніший отримує conflict. Correction помилки identity/прочитання джерела не оголошує весь документ хибним автоматично: вона відкликає old record; SourceWithdrawalGate створюється лише для явно підтвердженого source-level withdrawal у визначеному scope.

| Capability | Дозволено | Обмеження |
| --- | --- | --- |
| Schema administrator | Доставка reviewed schema versions через код/міграції | Не довільний Python/SQL/URL fetch у конфігурації; schema update не перепубліковує записи |
| Relation editor | Read scoped records, draft/import/submit | Explicit view/add/change grants і доступ до всіх participants; не може submit чужі приховані IDs або підтвердити payload status=approved |
| Domain reviewer | Підтвердити джерело/формуляцію/ціль конкретної revision | Explicit review capability і country/type scope; не тотожне staff чи власнику API token |
| Site publisher | Увімкнути approved revision свого site, unpublish | Не обходить domain/language/publication gates; shared approval для кількох affected sites потребує platform administrator за AGRO-2 |
| Block editor/publisher | Підготувати/активувати scoped block config | Окремі grants, тільки дозволені types/roles/slots; конфігурація не надає доступ до прихованих entities |

Усі write paths (Admin/API/import/bootstrap) використовують одну service/policy. Legacy own-post capability не стає relation review/schema/publish capability. Access до джерел і audit обмежений; public API повертає тільки дозволене source citation, не reviewer identity/внутрішні нотатки. preview приватний, no-store/noindex, з явним scope; не кешується разом із live.

Mutation вимагає `If-Match` lock_version; відсутній — 428, застарілий — 409, жодного lost update. Approval перевіряє base revision, source/schema version, identity projection, current eligibility_epoch і поточний participant scope повторно під lock. Єдиний lock order: schema/type (також correction graph/source withdrawal ledger) → entity/cultivar uniqueness locks за sorted UUID → identity keys і records за sorted UUID/key → revision/release. Correction/withdrawal batch бере весь набір locks у цьому порядку; target-record creation не змінює порядок після часткового захоплення. Довільних HTTP requests під DB locks немає. Member access перевіряється знову у транзакції. Stale submission або незмінний payload іншого actor не дає права approve.

Нова revision не замінює live; release pointer змінюється атомарно після всіх checks. Усі affected publications видимі reviewer до shared approval; запис effect list/hash входить до approval і звіряється знову при commit. Новий affected site між preview й approval робить preview stale.

## 6. Public selector і декларативні блоки

Одна service `select_related_catalog(context, block_config)` для HTML, public API, facets/counts і preview з окремою policy. Context містить verified site key, locale/content policy, country, as_of, page entity/crop. Не беремо довільний Host/locale/country зі значення payload без resolver. Job без context відхиляється.

Selector починає з **однієї approved/released revision одного record** і прикладає всі predicates до неї: preparation + crop + target + country + method. Реалізація через correlated EXISTS/joins, прив’язані до того самого revision ID. Окремі Post.filter по crop й target з різних records заборонені. Невідомий/неприпустимий filter — 400 у API або порожній результат із помилкою форми в HTML; фільтр не ігнорується і добірка не розширюється.

Обов’язкові gates до dedup/count/pagination: release enabled, record/entity active, withdrawn=false, superseded_by=NULL, created_epoch=approval_epoch=current eligibility_epoch, немає blocked source-version digest або unresolved withdrawal scope, approved revision, чинна eligibility у country/time, доступні всі обов’язкові participants. Material resolver читає approved/live text і site publication AGRO-4/7, активних предків AGRO-5; майбутня дата, draft, інший site або заборонена мова виключають запис. Legacy und exception існує лише для поточної AgroMega за AGRO-2, не сертифікує uk і не створює hreflang. Відсутній multi-site adapter не замінюється фальшивим Post.site_id.

Дедуп карток за entity UUID після relation eligibility, перед pagination. На картці препарату кілька методів лишаються окремими details; один препарат — одна картка в добірці. Public response містить scoped canonical material URL. Relation/entity ID не стає новим indexable article URL.

Приклад **майбутнього** bounded config (не існуючий API payload):

```json
{
  "version": 1,
  "slot": "crop.related_preparations",
  "type": "plant_protection_application",
  "context_role": "crop",
  "result_role": "preparation",
  "filters": ["target", "method"],
  "country_policy": "resolved_market",
  "sort": "canonical_title_uuid",
  "page_size": 12,
  "empty": "hide",
  "presentation": "catalog_cards",
  "manual_replacement": "none"
}
```

Збережена BlockConfiguration також містить id, hub/page owner, site, locale, revision/version, enabled, ordering. Config version=1; тільки allowlisted fields/type/roles/slots/sort/presentation, max 20 cards/page і 3 blocks/page, max 50 IDs у приватному filter batch, unknown keys rejected. Значення limit — перевірюваний execution budget, а не довільний ORM. Не підтримуються SQL, Python, regex, template path, external URL, nested query language або caller-supplied permission predicate. Редакторські labels локалізуються окремо від code/UUID.

Page adapters: crop підставляє crop; problem вимагає явно обрану crop, якщо вона не одна в scoped context; preparation підставляє preparation; cultivar спершу розв’язує approved cultivar_of. Другу культуру/type налаштовують даними/schemas, без Python branch за slug/PK. Unknown page/entity mapping приховує блок.

Manual migration: default залишає existing Guide/HTML. Dry-run зіставляє конкретні placement/slot, редактор явно активує replacement для цього slot. В одному slot рівно один renderer (manual або automatic), збережені manual IDs/content не видаляються. Feature off повертає manual view для slot; не копіює посилання в усі сорти. Порожній automatic блок приховується; повернення manual робиться лише явним mode, щоб не видати неперевірений fallback як regulatory факт.

Filters мають labels/reset/pagination, keyboard focus і mobile layout. Query variants канонікалізуються до чинної базової сторінки і noindex; не додаються до sitemap чи hreflang. Hidden cards/source text не можуть потрапити у counts або facet labels.

## 7. API й безпечний імпорт

Запропонований приватний namespace `/api/content/catalog/`; API версія явно 1 у representation. Existing posts/hubs/parser endpoints не змінюються від цього дизайну.

| Route | Поведінка |
| --- | --- |
| GET entity-types, relation-types | Read-only published schema metadata з permission scope |
| GET entities; GET relations/{uuid}; GET revisions | Пагіновані scoped records, version/ETag, історія лише з правом view |
| POST relations; POST relations/{uuid}/revisions | Створення draft/sealed revision; 201 або idempotent replay; status/reviewer із payload не довіряються |
| POST revisions/{uuid}/submit, /review | Окремі actions; reject/approve за capability, If-Match, source/base checks |
| POST relations/{uuid}/release, /unrelease, /archive | Explicit site scope й audit; approved review не дорівнює release |
| POST relations/{uuid}/correct-identity | Explicit old/target preconditions, canonical key, idempotency receipt; atomарний successor draft/reference + global withdrawal old; не звичайний import |
| POST relations/{uuid}/withdraw, /reinstate | Global record eligibility gate, epoch/source evidence і explicit capabilities; reinstate не release; old revisions не оживають |
| POST source-withdrawals; POST source-withdrawals/{uuid}/reconcile | Canonical source digest + explicit type/country scope; atomic affected-record withdrawal і durable quarantine за потреби; reconciliation не скасовує blocked source-version gate |
| POST imports/dry-run; POST imports/apply | Bounded batch, canonical digest і stable keys; dry-run без запису business data, apply повторно перевіряє все |
| GET imports/{receipt}; GET audit | Scoped readback/result; raw source/private notes не видаються публічно |
| GET/POST block-configurations, revision/release actions | Спільний revision/policy service; не raw update активного JSON |

Private batch: максимум 50 records/request, cursor-based result pages з deterministic ordering, кожен request має operation key і payload digest. Dry-run повертає per-item create/noop/conflict/error, mapping/schema/base digests; він не резервує право майбутнього запису. Apply звіряє digest, If-Match і permissions, створює тільки drafts, у межах одного batch атомарно (будь-яка error — rollback цього batch). Різні batches мають окремі receipts; resume не повторює успішні batches. Повтор ключа+payload повертає той самий результат, іншого payload — 409. Receipt/result записуються в тій самій транзакції; після невідомого transport outcome спершу readback, без blind retry.

Дублі обмежує semantic DB unique незалежно від operation keys/actor. Конфлікт із approved revision не переписує її. Bootstrap створює лише versioned schemas/config drafts за stable code; не seed реальних відповідностей із пілотних HTML. Помилки 400 validation, 401 token, 403 capability, 404 scoped invisible resource, 409 stale/semantic conflict, 428 missing precondition. Public related-catalog endpoint окремий, read-only, без приватних drafts та audit.

## 8. Індекси, часові межі й кеш

AGRO-74: unique keys вище; indexes participant(entity_id, role, revision_id), participant(revision_id, role, entity_id), revision(record_id, review_state), release(site_id, enabled, record_id, approved_revision_id). AGRO-85: country+regulatory_state+valid_from+valid_until+revision_id; method+revision_id; authority+registration record+application locator. Keyset pagination має canonical_title+entity UUID; сортування працює над resolved material, не приватним draft title.

Budget для нового selector, без SQL базової сторінки: ≤8 queries для 1 block/20 cards, ≤16 для 3 blocks/60 cards (shared context/resolver, bounded bulk loads); cold/warm counts вимірюються окремо, n=1/20 і 3 blocks без N+1. План SQL на ізольованих синтетичних 10k applications має показати використання scoped participant/release paths, без per-card fetching. Ці числа — acceptance budget, не заміри поточного коду. Перевищення потребує оптимізації або окремого reviewed budget change.

Кожен result page заповнюється після gates/dedup; якщо candidate cache містить лише неповну/відсічену сторінку, selector повторює scoped DB query для повного eligible page і count. Не обрізати candidate IDs до перевірки: це дає неправильні сторінки й counts навіть без витоку приватних даних.

На першому етапі **не кешувати кінцевий public eligibility, counts, HTML або serialized cards нових блоків**. Cache лише candidate UUIDs/schema/config із namespace `site/locale/country/type/policy/schema/generation/filter/page`. На кожному запиті повторно застосовувати eligibility, dates, active ancestors і approved publication до всіх candidate IDs; stale candidate cache не може повернути приховане. Candidate cache miss/неповнота після invalidation виправляється synchronous query. Caches existing crop context не повинні містити фінальні нові blocks: їх будують після cached context.

Commit relation/release/entity/mapping/material/category/config changes, identity correction та withdrawal/reinstate атомарно збільшує durable generation/outbox у owning DB для всіх affected sites. AGRO-10 забезпечує scoped generation і fan-out, у тому числі bulk SQL; rollback транзакції не публікує generation. Поки durable invalidation adapter не реалізований/перевірений, candidate cache вимкнений. `on_commit` signal сам по собі недостатній для cross-process/bulk SQL гарантії. Off-switch/restore не очищує withdrawal ledger, epochs або correction edges; recovery не повертає eligibility старим revisions.

Expiry працює від fresh eligibility predicate/as_of, без save чи worker. Для будь-якого майбутнього result cache обов’язковий TTL до найближчої publication/start/expiry boundary та synchronous guard; це окремий reviewed optimization. AGRO-73 не вводить cron як умову приховування простроченого запису.

## 9. Інтеграційна карта й порядок

| Власник | Контракт сумісності | Prerequisite gate для relation feature |
| --- | --- | --- |
| AGRO-2 | Відновлений accepted ADR, поточна AgroMega, und exception, shared body/roles | Джерело правил наявне; незалежний AGRO-73 review ще потрібен; старі audit counts не є live даними |
| AGRO-4 | Одна CatalogEntity, nullable Post.entity, approved revision/canonical material resolver | Entity/mapping slice до AGRO-74 migrations; text/publication resolver до public relation activation |
| AGRO-5 | Category.entity crop adapter спільно з AGRO-74; scoped category/hub/canonical/ancestors | Public activation і multi-site config залежать від перевіреного adapter; existing OneToOne не обходити другим hub |
| AGRO-7 | Спільні role/pending/live policies, atomic writers, compatibility API | Relation Admin/API використовує ці capabilities; private drafts можна реалізувати після конкретного permission adapter, без broad staff fallback |
| AGRO-9 | Product.post/Variety.publication/source keys збережені, explicit scoped app selectors | Потрібен лише для adapters цих app; seller prices не prerequisite domain schema й не regulatory доказ |
| AGRO-10 | Scoped public reads/index/cache generation, synchronous eligibility | Candidate caching/public integration gate; до нього cache disabled. Власний parallel search index не створюємо |
| AGRO-74, AGRO-75, AGRO-76, AGRO-77 | Model/constraints → Admin → import/API на одній service | Shared foundation, permissions/concurrency/import integration до AGRO-85 повного AC-04 |
| AGRO-78, AGRO-80, AGRO-81 | Same-revision query → bounded config → page adapters | До public блоків AGRO-85; domain validator не дублює query/renderer |
| AGRO-82 | Інтегровані shared acceptance сценарії | База для незалежного AGRO-85 приймання, не заміна його T-01–15 |

Порядок: review/accept AGRO-73 → entity/mapping slice AGRO-4 → AGRO-74 shared model/constraints → AGRO-75/76/77/78/80/81 у відповідних межах → AGRO-85 domain extension/fixtures/docs → integrated independent acceptance. AGRO-5/7/10 adapters підключаються перед відповідною public/write/cache межею, а не безумовно «всі задачі мають бути Done до аналізу».

Цей план не виконує суміжні задачі й не змінює їхній scope, assignee або стан. Native Plane dependency API раніше встановлено unavailable; ця таблиця є explicit dependency contract, не твердження про server enforcement. Scope transfer/shared schema approval, implementation authorization і acceptance лишаються окремими діями.

## 10. Активація, міграція й recovery

1. Ізольована Compose PostgreSQL/cache копія, нові pre/post manifests Post/Category/Product/Variety/Guide PK/FK/owners/attributes/URL; без production та Plane DB. Read-only snapshot не викликає write-capable get_absolute_url.
2. Additive shared entities/revisions/constraints і nullable mappings, feature off. Bootstrap schemas idempotent; mapping тільки за reviewed manifest. Немає автоматичних links із title/дерева/діючої речовини/пілотного HTML.
3. Private draft writes, negative SQL/concurrency/import/permissions tests; dry-run повторюється після interruption. Перевірити duplicate same-method і дозволені different-method records.
4. Shadow selector і page/config preview на synthetic crop A/B; eligibility/canonical/und/site parity; query budgets; тільки після цього окреме scoped enabling.
5. Explicit slot switch для manual→automatic; off-switch перевіряє повернення manual без видалення його даних. Реальні джерела/відповідності та production population потребують нового source review й окремого доручення.

Recovery R0 (до нових writes/releases): feature off, нові таблиці залишаються, mappings не руйнуються. R1 (після revisions/releases): off-switch presentation, approved-only compatibility readers/writers і visibility guards залишаються; private pending не копіюється у live Post/Guide. Якщо сумісний guarded writer недоступний — **і read, і write** paths relations закриті, а не повернуті до безконтрольного legacy renderer. Manual старі посилання не стають новою сертифікацією. R2 destructive schema rollback/restore — окреме maintenance рішення з freeze/reconciliation усіх нових revisions, не звичайне reverse migration. Off-switch не скасовує site publication, language чи regulatory gates.

Наявні URL, PK, authorship, comments/photos/tags/attributes, Product.post/Variety.publication, Guide placements і manual HTML залишаються. Не міняються legacy status-detail access, Nginx/forum/OIDC, залежності Parser Studio або runtime services. Commit/push/deploy у AGRO-73 не виконуються.

## 11. Перевірка контракту: приклади й негативні сценарії

Приклади нижче синтетичні. Назви препаратів у AGRO-85 — regression labels, не підтверджений дозвіл чи source review.

| Case | Вхід | Очікуваний результат / owning verification |
| --- | --- | --- |
| S1 simple symmetric | related_to(A,B), потім related_to(B,A) | Один logical record; нова спроба noop/conflict, не друга pair; self A,A invalid — AGRO-74 |
| S2 multi-party | prep P/crop C/target D/country X/method spray | Один revision-correlated факт, вибірка C+D+X повертає P — AGRO-78/85 |
| S3 false intersection | P+C+D1 і P+C2+D2; filter C+D2 | Порожньо, без перетину різних records — AGRO-78/85 T-13 |
| S4 ambiguous group | P+C+target=NULL, source «комплекс шкідників» | Без exact disease/pest facets; джерельний текст не розкладається — AGRO-85 T-03/04 |
| S5 identity | Одна речовина, різні formulation entities | Немає успадкування/merge; same-title rows не identity — AGRO-74/85 T-05 |
| S6 methods/source | Той самий P/C/D, spray і soil; repeated/parallel import | Два records; повтор/конкурентний дубль того самого ключа — один; source version нова pending revision — AGRO-76/85 T-06/09 |
| S7 approval isolation | Approved R1, pending R2, stale approve R0 | Public бачить R1; stale action 409; source withdrawal відсікає R1 негайно — AGRO-75/77/85 T-10/12 |
| S8 permissions | Nonstaff/staff без grants, чужий participant ID, status=approved | Немає escalation через endpoint/Admin/import/direct payload — AGRO-75/77 |
| S9 visibility | Draft/future/private entity material, inactive ancestor, foreign site/locale/country, unknown dates | Немає картки/count/facet/snippet; legacy und лише в дозволеному AgroMega adapter — AGRO-5/7/78/85 T-08 |
| S10 time/cache | Warm candidates, expiry midnight, worker stopped; category unpublish bulk SQL | Fresh gates приховують; durable generation прибирає stale candidate set; без generation cache off — AGRO-10/85 T-10/11 |
| S11 cultivar | cultivar V→C і V2→C2; немає явного зв’язку V3 | V має «Для культури C», V2 не отримує C; V3 без блоку; competing crop approval conflict — AGRO-74/85 T-07 |
| S12 UI/SEO | Другий crop, invalid filter, empty, page/reset, keyboard/mobile | Немає hardcoding, broadening, empty block; одна canonical/noindex query variants — AGRO-80/81/85 T-15 |
| S13 recovery | R0/R1 із pending, bootstrap twice, feature off/on | PK/FK/URL/attributes не змінені; pending не live; дані/історія відновлювані — AGRO-74/82/85 T-14 |
| S14 constraints | Direct SQL missing required role, bad kind, wrong release revision, edit sealed revision | Commit відхилено DB guard, не лише API validation — AGRO-74 |
| S15 budgets | 1/20 cards, 1/3 blocks, 10k applications | ≤8/≤16 SQL, немає лінійного per-card fetch; виміри зберегти — AGRO-78/82 |
| S16 identity correction | P1→P2 або unresolved target→exact target; existing target, повторний/паралельний corrected-key import | Revision під old key — 409/DB reject; correct-identity дає один successor-key record; старі releases всіх sites withdrawn, навіть коли successor draft; existing target не overwrite/release; A→B/B→A cycle і stale If-Match відхилено — VERIFY-01 |
| S17 durable withdrawal | R1 approved/released на A/B; withdraw; повторний release/reapprove R1, unarchive, replay receipt | Обидва sites без карток/count/facets; R1 неeligible назавжди через старий epoch; local unrelease не видається за withdrawal; stale candidate cache/зупинений worker не обходять gate — VERIFY-02 |
| S18 controlled reinstatement | Withdrawal E1; нова candidate R2; ще одна E2 паралельно з review/reinstate/release | Після E2 R2 stale/409; потрібна нова revision/new evidence. Reinstate поточного epoch із належними правами не включає releases; повтор old revision/blocked source digest заборонено; superseded record не reinstate — VERIFY-02 |
| S19 document scope | Один blocked source-version digest у кількох records, concurrent import після withdrawal | Усі відомі affected records блокуються атомарно; new import blocked digest відхилено; при невідомому scope відповідний type/country public feature fail-closed до reconciliation — VERIFY-02 |

Maker AGRO-73 перевіряє повноту цих правил і посилань; SQL/runtime/UI результати тут не заявлені. Незалежний reviewer має зіставити criteria AGRO-73 із цим документом, джерелами та AGRO-2. Acceptance AGRO-85 додатково вимагає своїх 10 AC і 15 tests на реалізованому exact snapshot.

## 12. Відкриті gates й відхилені альтернативи

- Контракт AGRO-73 прийнято. AGRO-85 потребує реалізації спільної моделі AGRO-74 і відповідних адаптерів.
- AGRO-4/5/7 мають погоджений behavior, але не готові entity/publication/canonical/permission adapters. До їх перевірки відсутню гарантію не підміняють current DB ownership або `is_staff`.
- Реальні country/timezone/method словники, source identity/provenance й regulatory review заповнюються окремо; цей контракт задає правила unknown/fail-closed, але не сертифікує пілот.
- Конкретні account grants, source reviewer, rollout operator і production country scope не призначені. Query budgets мають бути виміряні при реалізації; performance PASS не заявлено.
- Відхилено GFK на довільну модель (немає достатнього FK/integrity contract), дублювання entities у relations, окремий AGRO-85 CRUD/renderer, title/active-ingredient inference, live mutation approved payload, універсальний executable query language і TTL-only приховування приватних/прострочених даних.
- Forum/міжнародний застосунок/production launch не входять до цієї задачі. Незалежний review не виконується maker-ом; Done не встановлюється.
