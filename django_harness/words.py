class WordUtilsMixin(object):
    def generate_html_text(self, words, template='<div>%s</div>',
        truncated=False):

        words = ' '.join(["word%s" % (i+1) for i in range(words)])

        if truncated:
            words += ' ...'

        return template % words
