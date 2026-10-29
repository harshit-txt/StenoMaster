"""
Automated tests.  Run them with:   python manage.py test

They check the marking rules, register / login, the admin password lookup and the
whole listen -> reading -> typing -> submit -> result flow.
"""
import tempfile

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import checker
from .accounts import create_account
from .models import Assignment, Submission, UserProfile, WeakWord

PASSAGE = ("The appellant applied for the funds. Respondent No. 1 is the nominee in Mumbai, "
           "and the Honourable Court said ten people came.")


def tmp_media():
    return override_settings(MEDIA_ROOT=tempfile.mkdtemp())


# --------------------------------------------------------------------------
class CheckerTests(TestCase):
    def check(self, typed, original=PASSAGE):
        return checker.compare_texts(original, typed)

    def test_perfect(self):
        r = self.check(PASSAGE)
        self.assertEqual(r['mistakes'], 0)
        self.assertEqual(r['accuracy'], 100.0)

    def test_spacing_commas_and_quotes_are_ignored(self):
        r = self.check("The  appellant applied for the funds . Respondent No. 1 is the nominee in Mumbai ,"
                       "\n and the Honourable Court said ten people came .")
        self.assertEqual(r['mistakes'], 0)

    def test_other_punctuation_ignored_but_full_stop_counts_half(self):
        r = self.check(PASSAGE.replace(',', ''))            # comma dropped: ignored
        self.assertEqual(r['mistakes'], 0)
        r = self.check(PASSAGE.replace('funds.', 'funds'))  # full stop dropped: half
        self.assertEqual((r['punct'], r['mistakes']), (1, 0.5))

    def test_missing_word_is_full_and_does_not_shift_the_rest(self):
        r = self.check(PASSAGE.replace('applied ', ''))
        self.assertEqual((r['missing'], r['wrong'], r['extra'], r['mistakes']), (1, 0, 0, 1.0))

    def test_extra_and_repeated_word_is_full(self):
        r = self.check(PASSAGE.replace('the nominee', 'the the nominee'))
        self.assertEqual((r['extra'], r['mistakes']), (1, 1.0))

    def test_wrong_word_is_full(self):
        r = self.check(PASSAGE.replace('funds', 'money'))
        self.assertEqual((r['wrong'], r['mistakes']), (1, 1.0))

    def test_misspelling_is_half(self):
        r = self.check(PASSAGE.replace('appellant', 'appelant'))
        self.assertEqual((r['spelling'], r['wrong'], r['mistakes']), (1, 0, 0.5))

    def test_singular_plural_is_half(self):
        r = self.check(PASSAGE.replace('people', 'peoples'))
        self.assertEqual((r['spelling'], r['mistakes']), (1, 0.5))

    def test_incomplete_word_is_full(self):
        r = self.check(PASSAGE.replace('appellant', 'appel'))
        self.assertEqual((r['wrong'], r['mistakes']), (1, 1.0))

    def test_capital_letter_missing_is_half(self):
        r = self.check(PASSAGE.replace('Mumbai', 'mumbai'))
        self.assertEqual((r['capital'], r['mistakes']), (1, 0.5))

    def test_whole_word_in_capitals_is_full(self):
        r = self.check(PASSAGE.replace('Court', 'COURT'))
        self.assertEqual((r['wrong'], r['mistakes']), (1, 1.0))

    def test_figures_as_digits_or_words_and_variants_are_accepted(self):
        r = self.check(PASSAGE.replace('ten', '10').replace('Honourable', "Hon'ble"))
        self.assertEqual(r['mistakes'], 0)

    def test_misspelling_plus_missing_full_stop_is_one_mistake(self):
        r = self.check(PASSAGE.replace('funds.', 'fundz'))
        self.assertEqual((r['spelling'], r['punct'], r['mistakes']), (1, 1, 1.0))

    def test_accuracy_uses_original_word_count(self):
        r = self.check(PASSAGE.replace('funds', 'money'))        # 1 mistake in 22 words
        self.assertEqual(r['total_words'], 22)
        self.assertEqual(r['error_pct'], round(1 / 22 * 100, 2))
        self.assertEqual(r['accuracy'], round(100 - 1 / 22 * 100, 2))

    def test_empty_typed_text(self):
        r = self.check('')
        self.assertEqual((r['missing'], r['accuracy']), (22, 0.0))

    def test_weak_words_only_wrong_or_spelling(self):
        r = self.check(PASSAGE.replace('appellant', 'appelant').replace('funds', 'money')
                       .replace('applied ', '').replace('Mumbai', 'mumbai'))
        self.assertEqual(sorted(checker.weak_word_candidates(r['diff'])), ['appellant', 'funds'])


# --------------------------------------------------------------------------
class AccountTests(TestCase):
    def setUp(self):
        cache.clear()

    def register(self, **over):
        data = {'full_name': 'Rahul Sharma', 'username': 'rahul_s', 'phone': '98765 43210',
                'password': 'secret1', 'confirm_password': 'secret1'}
        data.update(over)
        return self.client.post(reverse('register'), data)

    def test_register_then_login_with_phone_and_with_username(self):
        r = self.register()
        self.assertRedirects(r, reverse('practice'))
        profile = UserProfile.objects.get(phone='9876543210')
        self.assertEqual(profile.role, 'student')
        self.assertEqual(profile.plain_password, 'secret1')
        self.client.post(reverse('logout'))
        for ident in ('9876543210', '+91 98765 43210', 'rahul_s', 'RAHUL_S'):
            r = self.client.post(reverse('login'), {'identifier': ident, 'password': 'secret1'})
            self.assertRedirects(r, reverse('practice'), msg_prefix=ident)
            self.client.post(reverse('logout'))

    def test_register_validation(self):
        self.register()
        self.client.post(reverse('logout'))
        self.assertContains(self.register(username='RAHUL_S', phone='9000000001'), 'already taken')
        self.assertContains(self.register(username='other', phone='9876543210'), 'already registered')
        self.assertContains(self.register(username='o2', phone='12345'), 'valid 10-digit')
        self.assertContains(self.register(username='o3', phone='9000000002', confirm_password='x'), 'do not match')
        self.assertContains(self.register(username='o4', phone='9000000003', password='abc', confirm_password='abc'),
                            'at least 6')
        self.assertEqual(User.objects.count(), 1)

    def test_no_email_or_role_field_on_register_page(self):
        html = self.client.get(reverse('register')).content.decode().lower()
        self.assertNotIn('name="email"', html)
        self.assertNotIn('name="role"', html)

    def test_wrong_password_and_lockout(self):
        self.register()
        self.client.post(reverse('logout'))
        for _ in range(8):
            r = self.client.post(reverse('login'), {'identifier': '9876543210', 'password': 'nope'})
            self.assertContains(r, 'Wrong phone number or password')
        r = self.client.post(reverse('login'), {'identifier': '9876543210', 'password': 'secret1'})
        self.assertContains(r, 'Too many wrong attempts')

    def test_password_change_updates_login_and_admin_copy(self):
        self.register()
        r = self.client.post(reverse('change_password'), {
            'current_password': 'secret1', 'new_password': 'newpass9', 'confirm_password': 'newpass9'})
        self.assertRedirects(r, reverse('profile'))
        self.assertEqual(UserProfile.objects.get(phone='9876543210').plain_password, 'newpass9')
        self.client.post(reverse('logout'))
        r = self.client.post(reverse('login'), {'identifier': '9876543210', 'password': 'newpass9'})
        self.assertRedirects(r, reverse('practice'))

    def test_footer_shows_admin_contact_everywhere(self):
        for name in ('landing', 'login', 'register'):
            html = self.client.get(reverse(name)).content.decode()
            self.assertIn('92118 94802', html, name)
            self.assertIn('tel:+919211894802', html, name)
            self.assertIn('Contact if you forgot your password or have any issues.', html, name)

    def test_logged_out_user_is_sent_to_login(self):
        r = self.client.get(reverse('practice'))
        self.assertRedirects(r, reverse('login') + '?next=' + reverse('practice'))


# --------------------------------------------------------------------------
class OwnerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = create_account(username='boss', full_name='The Boss', phone='9211894802',
                                    password='ownerpass', role='owner')
        self.rahul = create_account(username='rahul_s', full_name='Rahul Sharma', phone='9876543210',
                                    password='rahulpw1')
        self.priya = create_account(username='priya', full_name='Priya Singh', phone='9123456780',
                                    password='priyapw2')

    def test_owner_logs_in_with_phone_and_lands_on_admin(self):
        r = self.client.post(reverse('login'), {'identifier': '92118 94802', 'password': 'ownerpass'})
        self.assertRedirects(r, reverse('owner_dashboard'))

    def test_student_cannot_open_owner_pages(self):
        self.client.login(username='rahul_s', password='rahulpw1')
        for name in ('owner_dashboard', 'owner_students', 'upload_assignment'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_owner_sees_every_password_and_can_search(self):
        self.client.login(username='boss', password='ownerpass')
        html = self.client.get(reverse('owner_students')).content.decode()
        self.assertIn('rahulpw1', html)
        self.assertIn('priyapw2', html)
        self.assertNotIn('ownerpass', html)             # owners are not listed
        by_phone = self.client.get(reverse('owner_students'), {'q': '98765'}).content.decode()
        self.assertIn('rahulpw1', by_phone)
        self.assertNotIn('priyapw2', by_phone)
        by_name = self.client.get(reverse('owner_students'), {'q': 'priya'}).content.decode()
        self.assertIn('priyapw2', by_name)
        self.assertNotIn('rahulpw1', by_name)
        both = self.client.get(reverse('owner_students'), {'q': 'rahul 43210'}).content.decode()
        self.assertIn('rahulpw1', both)
        none = self.client.get(reverse('owner_students'), {'q': 'rahul 99999'}).content.decode()
        self.assertIn('No students found', none)

    @tmp_media()
    def test_owner_uploads_edits_and_deletes_assignment(self):
        self.client.login(username='boss', password='ownerpass')
        audio = SimpleUploadedFile('d.mp3', b'ID3' + b'\0' * 2000, content_type='audio/mpeg')
        pdf = SimpleUploadedFile('s.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        r = self.client.post(reverse('upload_assignment'), {
            'title': 'Set 1', 'category': 'progressive', 'date': '2026-10-01', 'base_wpm': 80,
            'paragraph_text': PASSAGE, 'audio_file': audio, 'strokes_pdf': pdf})
        self.assertRedirects(r, reverse('owner_dashboard'))
        a = Assignment.objects.get()
        self.assertEqual((a.word_count, a.category, a.created_by), (22, 'progressive', self.owner))
        self.assertTrue(a.audio_file.storage.exists(a.audio_file.name))
        # bad file types / missing audio are rejected
        bad = self.client.post(reverse('upload_assignment'), {
            'category': 'daily', 'date': '2026-10-02', 'base_wpm': 80, 'paragraph_text': PASSAGE,
            'audio_file': SimpleUploadedFile('x.txt', b'hello')})
        self.assertContains(bad, 'Upload an audio file')
        self.assertContains(self.client.post(reverse('upload_assignment'), {
            'category': 'daily', 'date': '2026-10-02', 'base_wpm': 80, 'paragraph_text': PASSAGE}),
            'required')
        # edit without touching files keeps them
        r = self.client.post(reverse('edit_assignment', args=[a.pk]), {
            'title': 'Set 1 (fixed)', 'category': 'progressive', 'date': '2026-10-01', 'base_wpm': 80,
            'paragraph_text': PASSAGE + ' Extra words here.'})
        self.assertRedirects(r, reverse('owner_dashboard'))
        a.refresh_from_db()
        self.assertEqual((a.title, a.word_count), ('Set 1 (fixed)', 25))
        self.assertTrue(a.audio_file and a.strokes_pdf)
        # remove the strokes PDF
        self.client.post(reverse('edit_assignment', args=[a.pk]), {
            'title': 'Set 1', 'category': 'progressive', 'date': '2026-10-01', 'base_wpm': 80,
            'paragraph_text': PASSAGE, 'remove_strokes': 'on'})
        a.refresh_from_db()
        self.assertFalse(a.strokes_pdf)
        # delete removes the file from disk
        name = a.audio_file.name
        storage = a.audio_file.storage
        self.client.post(reverse('delete_assignment', args=[a.pk]))
        self.assertFalse(Assignment.objects.exists())
        self.assertFalse(storage.exists(name))


# --------------------------------------------------------------------------
@tmp_media()
class FlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = create_account(username='boss', full_name='Boss', phone='9211894802',
                                    password='ownerpass', role='owner')
        self.student = create_account(username='rahul_s', full_name='Rahul Sharma', phone='9876543210',
                                      password='rahulpw1')
        self.assign = {}
        for cat in ('daily', 'progressive', 'kailashchand', 'short_dictation'):
            a = Assignment(title=f'{cat} one', category=cat, paragraph_text=PASSAGE, base_wpm=80,
                           created_by=self.owner)
            a.audio_file.save('d.mp3', SimpleUploadedFile('d.mp3', b'ID3' + bytes(range(256)) * 8), save=False)
            a.strokes_pdf.save('s.pdf', SimpleUploadedFile('s.pdf', b'%PDF-1.4 strokes'), save=False)
            a.save()
            self.assign[cat] = a
        self.client.login(username='rahul_s', password='rahulpw1')

    def test_lists_short_dictation_includes_daily(self):
        self.assertContains(self.client.get(reverse('progressive')), 'progressive one')
        self.assertNotContains(self.client.get(reverse('progressive')), 'daily one')
        self.assertContains(self.client.get(reverse('kailashchand')), 'kailashchand one')
        html = self.client.get(reverse('short_dictation')).content.decode()
        self.assertIn('short_dictation one', html)
        self.assertIn('daily one', html)

    def test_practice_page_has_exactly_three_cards_and_no_ssc(self):
        html = self.client.get(reverse('practice')).content.decode()
        for text in ('Progressive', 'Kailashchandra', 'Short Dictation for Beginners'):
            self.assertIn(text, html)
        self.assertEqual(html.count('class="count"'), 3)
        for page in ('landing', 'login', 'register'):
            self.assertNotIn('ssc', self.client.get(reverse(page)).content.decode().lower())
        self.assertNotIn('ssc', html.lower())

    def test_full_flow_and_result_page(self):
        a = self.assign['progressive']
        self.assertContains(self.client.get(reverse('assignment', args=[a.pk])), 'id="player"')
        self.assertContains(self.client.get(reverse('assignment_reading', args=[a.pk])), '300')
        typing = self.client.get(reverse('assignment_typing', args=[a.pk]))
        self.assertContains(typing, 'steno-pad')
        self.assertContains(typing, 'Submit your assignment')
        self.assertNotContains(typing, 'Respondent No. 1')       # the answer must never be shown while typing

        typed = PASSAGE.replace('appellant', 'appelant').replace('funds', 'money').replace('applied ', '')
        r = self.client.post(reverse('submit_assignment', args=[a.pk]), {
            'typed_text': typed, 'wpm_used': '100', 'client_seconds': '600'})
        sub = Submission.objects.get()
        self.assertRedirects(r, reverse('result', args=[sub.pk]))
        self.assertEqual((sub.wrong_count, sub.missing_count, sub.spelling_count), (1, 1, 1))
        self.assertEqual(sub.mistake_count, 2.5)
        self.assertEqual(sub.wpm_used, 100)
        self.assertEqual(sub.total_words, 22)

        html = self.client.get(reverse('result', args=[sub.pk])).content.decode()
        self.assertIn('d-wrong', html)
        self.assertIn('d-spelling', html)
        self.assertIn('d-missing', html)
        self.assertIn('<iframe', html)                           # strokes PDF viewer
        self.assertNotIn('hover', html.lower())
        self.assertNotIn('title=', html.split('Your transcript')[1].split('Stroke Techniques')[0])   # no tooltips

        # weak words saved (wrong + spelling only), shown on the weak words page
        words = dict(WeakWord.objects.filter(student=self.student).values_list('word', 'miss_count'))
        self.assertEqual(words, {'appellant': 1, 'funds': 1})
        wh = self.client.get(reverse('weak_words')).content.decode()
        self.assertIn('appellant', wh)
        self.assertNotIn('applied', wh)                          # missing words are not weak words

        # dashboard and practice page numbers
        self.assertContains(self.client.get(reverse('student_dashboard')), 'Recent sessions')
        practice = self.client.get(reverse('practice'))
        self.assertEqual(practice.context['streak'], 1)
        self.assertEqual(practice.context['today_rank'], 1)

        # second attempt: weak word counts add up
        self.client.post(reverse('submit_assignment', args=[a.pk]), {'typed_text': typed})
        self.assertEqual(WeakWord.objects.get(word='funds').miss_count, 2)

    def test_students_cannot_see_each_others_results(self):
        a = self.assign['daily']
        self.client.post(reverse('submit_assignment', args=[a.pk]), {'typed_text': PASSAGE})
        sub = Submission.objects.get()
        create_account(username='other', full_name='Other', phone='9000000009', password='otherpw1')
        self.client.logout()
        self.client.login(username='other', password='otherpw1')
        self.assertEqual(self.client.get(reverse('result', args=[sub.pk])).status_code, 404)
        self.client.logout()
        self.client.login(username='boss', password='ownerpass')
        self.assertContains(self.client.get(reverse('view_submission', args=[sub.pk])), 'Rahul Sharma')

    def test_typing_clock_survives_refresh_and_resets_on_new_attempt(self):
        a = self.assign['daily']
        first = self.client.get(reverse('assignment_typing', args=[a.pk]))
        again = self.client.get(reverse('assignment_typing', args=[a.pk]))
        self.assertEqual(first.context['attempt_id'], again.context['attempt_id'])
        self.assertLessEqual(again.context['remaining_seconds'], 3000)
        session = self.client.session
        session[f'typing_start_{a.pk}'] -= 3000          # pretend the 50 minutes are over
        session.save()
        self.assertEqual(self.client.get(reverse('assignment_typing', args=[a.pk])).context['remaining_seconds'], 0)
        self.client.get(reverse('assignment', args=[a.pk]))      # listening again = fresh attempt
        self.assertGreater(self.client.get(reverse('assignment_typing', args=[a.pk])).context['remaining_seconds'], 2990)

    def test_media_needs_login_and_supports_range(self):
        a = self.assign['daily']
        url = a.audio_file.url
        full = self.client.get(url)
        self.assertEqual(full.status_code, 200)
        self.assertEqual(full['Accept-Ranges'], 'bytes')
        size = int(full['Content-Length'])
        part = self.client.get(url, HTTP_RANGE='bytes=10-19')
        self.assertEqual(part.status_code, 206)
        self.assertEqual(b''.join(part.streaming_content), (b'ID3' + bytes(range(256)) * 8)[10:20])
        self.assertEqual(part['Content-Range'], f'bytes 10-19/{size}')
        self.assertEqual(self.client.get(url, HTTP_RANGE=f'bytes={size + 5}-').status_code, 416)
        self.assertEqual(self.client.get('/media/../settings.py').status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_submit_requires_post(self):
        a = self.assign['daily']
        self.assertEqual(self.client.get(reverse('submit_assignment', args=[a.pk])).status_code, 405)
