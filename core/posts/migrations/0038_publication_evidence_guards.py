from django.db import migrations

INSTALL = """
CREATE FUNCTION posts_approval_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Publication approval evidence is immutable' USING ERRCODE='23514';
END $$;
CREATE TRIGGER posts_approval_immutable BEFORE UPDATE OR DELETE ON posts_postpublicationapproval
FOR EACH ROW EXECUTE FUNCTION posts_approval_immutable();

CREATE FUNCTION posts_publication_matches_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM posts_postpublicationapproval a
        WHERE a.id=NEW.approval_id AND a.post_id=NEW.post_id AND a.content_locale=NEW.content_locale
    ) THEN
        RAISE EXCEPTION 'Publication must match its material and reviewed content locale' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER posts_publication_approval BEFORE INSERT OR UPDATE ON posts_sitepostpublication
FOR EACH ROW EXECUTE FUNCTION posts_publication_matches_approval();
"""
REMOVE = """
DROP TRIGGER posts_publication_approval ON posts_sitepostpublication;
DROP FUNCTION posts_publication_matches_approval();
DROP TRIGGER posts_approval_immutable ON posts_postpublicationapproval;
DROP FUNCTION posts_approval_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("posts", "0037_postpublicationapproval_sitepostpublication_and_more")]
    operations = [migrations.RunSQL(INSTALL, REMOVE)]
