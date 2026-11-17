# Контракт ядра AgroMega: сайти, мови та сумісність

- Дата: 2026-10-23.
- Статус: **Accepted — контракт першого етапу**. Користувач прямо погодив рекомендовані рішення щодо спільних текстів, підтвердження мов і прав редакторів та доручив зафіксувати їх у контракті/плані й Plane. Це погодження поведінки та меж; реалізація, міграції й deployment не дозволені. Назви моделей і точні механізми revision/locking уточнюються в реалізаційному дизайні без зміни цих правил.
- Джерело: поточне доручення AGRO-2 — локальний запуск/аудит фактичних даних, мов і URL, без реалізації та міграції.
- Змінює напрям ADR `2026-09-06-separate-global-platform.md`; історичний текст того ADR залишається доступним.
- Задача та підсумки аудиту/погодження: [AGRO-2](http://localhost:8090/roar/projects/0f4660b9-fa20-4bc4-b738-1715493b6747/issues/8518ff9c-178c-4fcf-8b9d-12544ab7cab3).
- Task-scoped план і докази зберігаються локально у gitignored `var/agents-work/` за правилами репозиторію; вони не є tracked документацією.

## Факти, які визначають контракт

У локальній agrodb: 3 270 Post (3 267 active), 148 Category, 26 608 Variety, 3 035 Product, 20 companies.Company, 1 034 registry.Company, 3 757 Photo. Міграції поточного checkout уже застосовані; аудит не запускав migrate. Локальна копія не є доказом актуального production inventory.

Усі 3 270 збережених Post URL збігаються з `reverse` під uk та розпізнаються з тим самим PK. Три містять percent-encoded кирилицю; порівняння decoded request.path з encoded absolute_url дає self-301. Нормалізація адрес — окремий дефект сумісності, не підстава масово змінити slugs.

33 групи Post мають однаковий title. У Variety є 201 група повторюваних application_number; title+category дублів не виявлено. 50 Variety посилаються на 50 Post; 1 001 Product посилається на 210 Post. Решта не мають такого зв’язку. Це не повний entity mapping, і його не можна відновити лише за title або номером заявки.

У Django Site існують ID 2,4,5,6; активний SITE_ID runtime — 2. Модель Site не має active. FlatPage містить 7 сторінок і 25 site memberships, зокрема локальні Site IDs. Є один CategoryHub із site=NULL і locale="". Видалення «зайвих» Site або трактування blank hub scope як дозволу для майбутніх сайтів пошкодить сумісність.

## Обов’язкові інваріанти

1. Тільки поточна AgroMega активна після першого етапу. Наявність legacy Site row не активує публічний сайт; не створюється новий домен/ринок/застосунок.
2. Post PK, publisher/owner, comments/photo/tag/attribute, Product.post, Variety.publication і guide placements зберігаються. Ніякого автоматичного merge за title чи slug.
3. Core і forum лишаються окремими застосунками/БД; User/OIDC authority належить core. Cross-DB FK та новий forum source of truth не вводяться. Parser Studio працює тільки через API.
4. Мова інтерфейсу не визначає мову матеріалу. Усі legacy тексти лишаються доступними за попередніми правилами, навіть коли мову ще не підтверджено. Ніяких автоматичних перекладів.
5. Public forum namespace за поточною інструкцією — `/forum/`. Реальний локальний `/community/` baseline зафіксований як невідповідність, яку треба виправити окремою реалізацією з URL/SSO compatibility перевіркою. Цей ADR не змінює proxy.

## Погоджені правила й schema-контексти

### Site

Повторно використати Django Site та owned SiteConfiguration. Stable site key не дорівнює request Host, ринку або числовому SITE_ID dev. Configuration має explicit active, canonical public origin, дозволені host aliases, enabled UI/content locales і feature policy. Поточні Site IDs/FlatPage memberships зберігаються; mapping локальних aliases документується, не робиться destructive merge.

Canonical public origin, browser integration base і OIDC issuer — **окремі ролі**. Зараз HOST=https://agromega.in.ua, SITE_URL=http://localhost:8000, forum base=http://localhost:8000/community. Не уніфікувати їх сліпим переписуванням домену. Issuer/sub/callback registrations не змінюються від додавання SiteConfiguration.

Невідомий/disabled host або job без scope має fail-closed у новому resolver. Поточний dev ALLOWED_HOSTS=['*'] повертає AgroMega з foreign-site.invalid — це baseline, не бажаний multi-site контракт. Тести нової поведінки мають явно відділяти dev convenience від production proxy trust.

### Ідентичність → матеріал → текст → публікація

- CatalogEntity: стабільний opaque key/type та provenance; існуючі Post і Variety IDs лишаються валідними source IDs. Mapping nullable, перевірений; ні original_name, ні title/application_number поодинці не є global unique entity key.
- Post: стабільна ідентичність матеріалу; optional entity reference. До окремої міграції зв’язків Product/Variety продовжують посилатися на Post. Реєстр без матеріалу не змушений породжувати Post/переклад.
- PostText: UNIQUE(post, locale); title/text/sources/base metadata та provenance редакційної версії. Назви сортів/original names не перекладаються автоматично. Legacy поля Post зберігаються як сумісний mirror до перевіреного cutover.
- SitePostPublication: UNIQUE(site, post, locale), посилання на відповідний PostText і UNIQUE(site, canonical_path); visibility/date/category binding/site SEO overrides. Text.post і locale мають відповідати publication. DB constraints + transactional service мають покривати cross-row consistency. Site visibility не змінює shared entity/text.
- Погоджено один спільний PostText на матеріал/мову. SitePostPublication керує site visibility, URL, рубрикою, датою та SEO-заголовком/описом; порожні site SEO поля використовують базові метадані тексту. Тіло тексту не має прихованих site-local overrides.
- Змістовно інша стаття тією самою мовою — окремий Post, пов’язаний із тією самою CatalogEntity, з явним походженням, якщо це похідний матеріал. Автоматичного синхронізування між незалежними матеріалами немає; нову систему site-local text variants у перший етап не додаємо.
- Перед редагуванням/затвердженням спільного тексту показувати всі публікації, які зачіпає зміна. Редактор готує пропозицію; до затвердження public readers бачать попередню затверджену версію. Це вимагає механізму pending revision/proposal та перевірки актуальності базової версії, а не прямого переписування live body. Точний owned storage механізм — реалізаційна деталь AGRO-4/7; гарантія live-version isolation обов’язкова.

### Мова й перевірка якості

Теперішні Post не мають language field; усі work_status=NULL. Символьна евристика дала 2 799 uk-marker candidates, 48 mixed-marker, 422 unresolved, 1 Latin-dominant. Це **не статистика підтверджених мов**. Ручний огляд 20 стратифікованих уривків підтверджує українську основу з російськими залишками; Latin-dominant Post 1681 — короткий український вислів із британськими топонімами, не англійська стаття.

Зберігати окремо primary locale (або `und`), review status, метод/версію/доказ, reviewed_by/date та ознаку змішаності. `mixed` — стан review/quality, не довільно вигаданий locale. `uk` лише після достатньої перевірки; уривковий agent review не є редакторською сертифікацією повного документа. Невідомі записи не відфільтровувати з поточної AgroMega. Legacy publication binding дозволяє und незалежно від UI locale, але не експортує його в нові сайти й не створює hreflang.

Релабелінг und→підтверджена locale має бути атомарним без зміни canonical path чи дублювання publication. Чинні `/en/` routes не використовувати як доказ існування PostText(en).

Погоджена мовна процедура першого етапу:

1. Legacy неперевірені матеріали отримують `und` і «потребує перевірки», зберігаючи доступність та URL. Автоматичний результат — окремий candidate/method/version/date, він не присвоює підтверджену мову.
2. Випусковий редактор підтверджує основну мову після перегляду **повного тексту конкретної версії**. Зберігати actor/date/revision identity; actor не призначається в цьому плануванні. Підтвердження уривка не сертифікує документ.
3. Українська основа з російськими залишками може мати `uk` і окрему позначку змішаності/потреби мовного редагування. Підтвердження основної мови не є підтвердженням редакційної якості.
4. Суттєва зміна body повертає мовний review на перевірку. Site SEO-only edit його не скидає. До приймання нової версії попередня live version та її перевірка лишаються чинними; новий review не підмінює стару версію автоматично.
5. Новий матеріал не можна вперше опублікувати без підтвердженої основної мови. Це новий workflow gate, який має бути застосований і до legacy API через сумісний adapter; старі payload/PK/url/auth зберігаються, але не дають обходу gate. Post-create response може означати створений draft, а не вже публічну сторінку; точний явний response/status контракт і оновлення клієнтів обов’язкові в AGRO-7 до перемикання.
6. Повна мовна перевірка всіх 3 270 legacy Post **не є критерієм завершення першого етапу**. Критерій — робоча модель/процедура збереження und, перевірки версій та public parity. Усі неперевірені legacy записи не знімаються з публікації через цей gate.

### Таксономія, хаби й службові сторінки

Category IDs/MPTT/global slugs лишаються. Локалізовані labels/meta відділяються від stable attributes/географічних кодів. SiteCategoryConfiguration керує presentation/navigation/visibility/canonical. CategoryHub OneToOne(category) замінюється сумісним site/locale-aware binding з збереженням hub/section IDs. Існуючий blank hub scope спочатку означає поточну legacy AgroMega, а не всі майбутні сайти. Guide sections/placements/preview мають явний scope зі збереженням ACL.

Flatpages і їхні існуючі 25 memberships входять в аудит Site mapping і URL parity. Policy/about/cookies/terms не можна випадково відкрити на новому disabled host або видалити разом із локальним Site alias. Окремі site-local юридичні тексти — наступне бізнес-рішення до запуску нового ринку.

## Visibility, ACL й URL fallback

Поточні три inactive Post (1374,1790,3556) виключені з public_posts/sitemap, але вибірковий detail GET повертає 200. Це зафіксована розбіжність. Не перетворювати status=False на новий definitive draft lifecycle і не приховувати ці URL побічно. Водночас відсутність site publication завжди забороняє foreign-site доступ. Розбіжності legacy status потребують окремої редакційної політики до нових lifecycle guarantees.

Legacy token API зберігає authenticated list/create, staff detail/update, publisher із token, IDs/payload compatibility через AgroMega adapter. Погоджені нові правила language/pending revision/publication застосовуються однаково до API та Admin: право створення або зміни запису не є обходом publication gate. Сумісність старих update capability забезпечується явним mapping до чинних AgroMega прав; майбутні sites grants автоматично не успадковуються. Admin/import/bulk paths проходять той самий transactional publication adapter. Саме старий implicit create→public contract уточнюється новим погодженим gate; клієнти мають отримати явний draft/publication status, а не хибну обіцянку public URL.

Погоджена матриця ролей:

| Роль | Дозволені дії | Межі |
| --- | --- | --- |
| Редактор сайту | Перегляд матеріалів свого сайту, пропозиції text/metadata edits і мовної перевірки | Не публікує зміни live самою дією редагування; не має чужого site scope |
| Випусковий редактор сайту | Затвердження змін у межах свого сайту, publish/unpublish своєї publication, підтвердження мови повного тексту | Зміна shared text, що зачіпає кілька сайтів, потребує адміністратора платформи |
| Адміністратор платформи | Сайти, права, спільні сутності; затвердження shared text edits, що зачіпають кілька сайтів | Не виконує auto merges, URL rewrites чи масове переприв’язування як звичайне редагування |

`is_staff` дає Admin access, не глобальні редакторські права на всі сайти. Поточним редакторам явно відображаються їхні нинішні capabilities на AgroMega, без blanket rights для нових sites. Це mapping існуючих прав, не автоматичне призначення всім staff ролі publisher. Ролі — capabilities контракту, а не призначення конкретним людям; account grants у цьому завданні не змінюються. Token/API і UI використовують ту саму scoped policy. Unpublish одного сайту не видаляє Post/Text/Entity й не знімає інші site publications.

`/en/` index зараз 200, Content-Language=en, html lang=uk; Post `/en/...html` у вибірці робить 301 до unprefixed canonical. Sitemap `/en/sitemap-main.xml` віддає ті самі 3 462 URL. Зберегти маршрутний контракт до окремого SEO рішення; не створювати мовні дублі чи hreflang. Canonical paths у БД лишаються encoded; порівняння з request.path має використовувати контрольовану нормалізацію без double decode, зі спеціальними tests для percent signs, Cyrillic і reserved separators. Self-301 для Post 9,2906,3016 — окремий repair case в майбутній URL задачі.

## Міграція й перевірка — лише план

Additive schema → dry-run mapping → restartable backfill → transactional legacy mirrors → shadow read comparison → scoped reads/index/cache → rollback rehearsal. Немає миграції або backfill в цьому AGRO-2 запуску. Поточні source manifests є доказовим baseline, але не замінюють новий pre-migration snapshot на дозволеній копії БД перед майбутнім виконанням.

SearchDocument synthetic PK не є source identity: працюючий worker періодично перебудовує індекс кожні 300 секунд; між двома аудитами source fingerprints незмінні, а search PK змінилися при незмінних 5 117 documents. Acceptance порівнює source IDs/URLs/visibility і scoped projection content, а не однакові surrogate PK індексу. Registry application numbers, source_product_key, валюти, match-status і lease/history semantics не змінюються від locale.

Усі 3 035 локальних Product наразі review, тому непорожній ринок/ціни не доведені цим runtime. Market sitemap порожній; нова реалізація потребуватиме окремих test fixtures eligible/expired/confirmed cases. Сьогодні fixtures у БД не створювались.

## Закриті рішення та наступні gates

Три продуктові рішення закриті прямим погодженням користувача: shared text/site publication; full-version language review із legacy und exception; explicit site-editor/publisher/platform-admin roles. Повторне погодження цих правил не потрібне.

Наступні технічні deliverables: pending revision concurrency/approval binding, точний API draft/publication response і сумісність клієнтів, permission mapping чинних користувачів, тести обходу gates та independent contract review. Це реалізаційне деталювання погодженої поведінки, не повторне відкриття продуктових рішень. Legacy inactive detail/status discrepancy лишається окремим baseline case без автоматичної зміни видимості. Призначення конкретних редакторів/міграція grants і виконання implementation потребують окремого доручення.

Forum `/forum/` — вже надана вимога, не запит на повторне погодження напряму. Потрібен окремий авторизований implementation scope із переходом aliases/callback/static/media/canonical/sitemap. Production publication launch додатково потребує Spirit/Mistune security gate. Жоден Planning/Ready статус не авторизує ці зміни.
