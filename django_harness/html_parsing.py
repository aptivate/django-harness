from __future__ import unicode_literals, absolute_import

from cssselect import GenericTranslator
from htmlentitydefs import name2codepoint
from lxml import etree
import six


class HtmlParsingMixin(object):
    def parse(self, response):
        if hasattr(response, 'parsed'):
            # already parsed
            return response.parsed

        from django.utils.safestring import SafeText
        if isinstance(response, SafeText) or isinstance(response, six.string_types):
            content = response
        else:
            from django.template.response import SimpleTemplateResponse
            if isinstance(response, SimpleTemplateResponse):
                response.render()

            if 'content' not in dir(response):
                raise Exception("Tried to parse response with no content: %s"
                    % response)
                # without setting response.parsed, so it blows up if you
                # try to access it.

            mime_type, _, charset = response['Content-Type'].partition(';')
            if mime_type != "text/html":
                return
                # without setting response.parsed, so it blows up if you
                # try to access it.

            if 'content' not in dir(response):
                raise Exception("Response is HTML but unexpectedly has no "
                    "content: %s: %s" % (response.status_code, response))

            content = unicode(response.content, 'utf-8')

        if hasattr(self, 'entity_cache'):
            entities = self.entity_cache
        else:
            #import twisted.lore
            #with open(os.path.join(twisted.lore.__file__, "xhtml-lat1.ent")) as f:
            #    entities = f.read()
            entities = ""
            for name, value in name2codepoint.iteritems():
                entities += '<!ENTITY %s "&#%d;">' "\n" % (name, value)
            self.entity_cache = entities

        # http://stackoverflow.com/questions/5170252/whats-the-best-way-to-handle-nbsp-like-entities-in-xml-documents-with-lxml
        import re
        xml = re.sub(r'(?m)^\s+', '', """
            <?xml version="1.0"?>
            <!DOCTYPE html [""" +
            entities +
            #<!ENTITY acute   "&#180;">
            #<!ENTITY copy    "&#169;">
            #<!ENTITY hellip  "&#8230;">
            #<!ENTITY mdash   "&#8212;">
            #<!ENTITY nbsp    "&#160;">
            #<!ENTITY ntilde  "&#241;">
            #<!ENTITY rsaquo  "&#8250;">
            #<!ENTITY shy     "&#173;">
            #<!ENTITY uuml    "&#252;">
            "]>") + re.sub(r"(?i)<!DOCTYPE html.*", "", content)
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)

        try:
            root = etree.fromstring(xml, parser)
        except SyntaxError as e:
            lineno = None

            import re
            match = re.match('Opening and ending tag mismatch: ' +
                '(\w+) line (\d+) and (\w+), line (\d+), column (\d+)', str(e))

            if match:
                lineno = [int(match.group(2)), int(match.group(4))]

            if lineno is None:
                match = re.match('.*, line (\d+), column (\d+)', str(e))
                if match:
                    lineno = [int(match.group(1))]
                else:
                    lineno = [e.lineno]

            if lineno is not None:
                lines = xml.splitlines(True)
                if len(lineno) > 1:
                    first_line = max(lineno[0] - 1, 1)
                    last_line = min(lineno[1] + 1, len(lines))
                else:
                    first_line = max(lineno[0] - 5, 1)
                    last_line = min(lineno[0] + 5, len(lines))
                try:
                    print xml
                except UnicodeEncodeError:
                    print xml.encode('ascii','xmlcharrefreplace')

                try:
                    print "Context (lines %d-%d):\n>>%s<<" % (first_line,
                        last_line, "".join(lines[first_line:last_line]))
                except UnicodeEncodeError:
                    print "Context (lines %d-%d):\n>>%s<<" % (first_line,
                        last_line, "".join([line.encode('ascii','xmlcharrefreplace')
                            for line in lines[first_line:last_line]]))
            else:
                print repr(e)

            raise e

        if 'content' in dir(response):
            response.parsed = root

        return root

    XHTML_NS = "{http://www.w3.org/1999/xhtml}"

    def xhtml(self, name):
        return "%s%s" % (self.XHTML_NS, name)

    def tostring(self, element):
        return etree.tostring(element, pretty_print=True)

    def find_within(self, parent, xpath, required=True, list=False):
        try:
            children = parent.xpath(xpath)
        except SyntaxError as e:
            import sys
            ex = sys.exc_info()
            raise ex[0], "Failed to execute XPath query: %s: %s" % \
                (xpath, ex[1]), ex[2]

        if required:
            self.assertNotEqual(0, len(children),
                "Failed to find '%s' in section:\n\n%s" %
                (xpath, self.tostring(parent)))

        if list:
            return children
        elif len(children) > 0:
            return children[0]
        else:
            return None

    def get_page_element(self, response, xpath, required=True):
        self.parse(response)
        self.assertIn('parsed', dir(response),
            "Last response was empty or not parsed: %s" % response)

        return self.find_within(response.parsed, xpath, required)

    translator = GenericTranslator()

    def query(self, response_or_element, selector, required=True, list=False):
        from django.utils.safestring import SafeText

        if 'content' in dir(response_or_element):
            # it's an HTTP response, so parse it to get root element
            ancestor = self.parse(response_or_element)
        elif isinstance(response_or_element, SafeText) or \
            isinstance(response_or_element, six.string_types):
            ancestor = self.parse(response_or_element)
        else:
            ancestor = response_or_element

        try:
            return self.find_within(ancestor,
                self.translator.css_to_xpath(selector), required, list)
        except self.failureException as e:
            raise self.failureException("Failed to find <%s> in section:\n%s" %
                (selector, e))

    def first_child(self, element, message=''):
        if message:
            message = message + ': '

        self.assertNotEqual(0, len(element), message +
            "%s does not have any children" % self.tostring(element))
        return element[0]

    def extract_error_message(self, response):
        self.parse(response)

        error_message = response.parsed.findtext('.//' +
            self.xhtml('div') + '[@class="error-message"]')

        if error_message is None:
            error_message = response.parsed.findtext('.//' +
                self.xhtml('p') + '[@class="errornote"]')

        if error_message is not None:
            # extract individual field errors, if any
            more_error_messages = response.parsed.findtext('.//' +
                self.xhtml('td') + '[@class="errors-cell"]')
            if more_error_messages is not None:
                error_message += more_error_messages

            # trim and canonicalise whitespace
            error_message = error_message.strip()
            import re
            error_message = re.sub('\\s+', ' ', error_message)

        # return message or None
        return error_message

    def assert_get_management_form(self, get_response_or_parent_element,
        prefix):

        """
        You need to make a GET request to get the current values of these
        fields. Pass the response to this method as `get_response`.
        """

        if hasattr(get_response_or_parent_element, 'content'):
            parent = self.parse(get_response_or_parent_element)
        else:
            parent = get_response_or_parent_element

        total = self.find_within(parent,
            './/input[@id="id_%s-TOTAL_FORMS"]' % prefix)
        initial = self.find_within(parent,
            './/input[@id="id_%s-INITIAL_FORMS"]' % prefix)
        max_num = self.find_within(parent,
            './/input[@id="id_%s-MAX_NUM_FORMS"]' % prefix)

        return dict(
            (element.get('name'), element.get('value'))
            for element in [total, initial, max_num]
        )

    def assertInHTML(self, needle, haystack, count = None, msg_prefix=''):
        if msg_prefix:
            msg_prefix = msg_prefix + ': '

        msg_prefix = haystack + "\n\n" + msg_prefix

        return super(HtmlParsingMixin, self).assertInHTML(needle, haystack,
            count, msg_prefix)

