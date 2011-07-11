# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2008 - 2011 by Wilbert Berendsen
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

"""
A simple persistent completion model (e.g. for QLineEdits).
"""


from PyQt4.QtCore import QSettings
from PyQt4.QtGui import QApplication, QStringListModel

_models = {}


def model(key):
    """Returns the model for the given settings key.
    
    A Model is instantiated if necessary.
    The model remains alive until the application exits, at which
    moment the data is saved.
    
    """
    try:
        return _models[key]
    except KeyError:
        m = _models[key] = Model(key)
        return m


class Model(QStringListModel):
    """A simple model providing a list of strings for a QCompleter.
    
    Instantiate the model with a QSettings key, e.g. 'somegroup/names'.
    Use the addString() method to add a string.
    
    The completions are saved when the application exits.
    
    """
    def __init__(self, key):
        super(Model, self).__init__()
        self.key = key
        self.load()
        QApplication.instance().aboutToQuit.connect(self.save)
        
    def load(self):
        self.setStringList(sorted(QSettings().value(self.key) or []))
    
    def save(self):
        QSettings().setValue(self.key, self.stringList())

    def addString(self, text):
        strings = self.stringList()
        if text not in strings:
            strings.append(text)
            strings.sort()
            self.setStringList(strings)
