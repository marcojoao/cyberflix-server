from __future__ import annotations

import hashlib


class CatalogWeb:
    def __init__(self, id: str, name: str, selected: bool = False):
        self.__id: str = id
        self.__uuid: str = hashlib.md5(self.__id.encode()).hexdigest()[:5]
        self.__name: str = name
        self.__selected: bool = selected
        self.__children: list[CatalogWeb] = []

    @property
    def id(self) -> str:
        return self.__id

    @property
    def uuid(self) -> str:
        return self.__uuid

    @property
    def name(self) -> str:
        return self.__name

    @property
    def is_selected(self) -> bool:
        return self.__selected

    def set_selected(self, selected: bool):
        self.__selected = selected

    @property
    def children(self) -> list[CatalogWeb]:
        return self.__children

    def add_child(self, child):
        self.__children.append(child)

    def to_dict(self):
        return {
            "uuid": self.__uuid,
            "name": self.__name,
            "isSelected": self.__selected,
            "children": [child.to_dict() for child in self.__children],
        }
