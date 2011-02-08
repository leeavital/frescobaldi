# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2008, 2009, 2010 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.

from __future__ import unicode_literals

"""
Manages a local temporary directory for a Document (e.g. unnamed or remote).
"""

import os
import shutil
import tempfile

import mode
import plugin


def scratchdir(document):
    return ScratchDir.instance(document)
    

class ScratchDir(plugin.DocumentPlugin):
    
    def __init__(self, document):
        self._directory = None
        
    def create(self):
        """Creates the local temporary directory."""
        self._directory = tempfile.mkdtemp()
    
    def delete(self):
        """Deletes our temporary area."""
        if self._directory:
            shutil.rmtree(self._directory, ignore_errors=True)
            self._directory = None
            
    __del__ = delete

    def directory(self):
        """Returns the directory if a temporary area was created, else None."""
        return self._directory
    
    def path(self):
        """Returns the path the saved document text would have if a temporary area was created, else None."""
        if self._directory:
            basename = None
            if not self.document().url().isEmpty():
                basename = os.path.basename(self.document().url().path())
            if not basename:
                basename = 'document' + mode.extension(mode.documentMode(self.document()))
            return os.path.join(self._directory, basename)
            
    def saveDocument(self):
        """Writes the text of the document to our path()."""
        if not self._directory:
            self.create()
        with open(self.path(), 'w') as f:
            f.write(self.document().encodedText())
            

